#!/usr/bin/env python3
"""
诊断 LLM / Embedding 认证失败。

用法：
    docker exec -it claw-backend python diagnose_key.py
    docker exec -it claw-backend python diagnose_key.py --key sk-xxx   # 直接测某个 Key

会打印：
  · 对话与向量各自的端点、Key 指纹（长度/首尾字符/是否含空白）
  · 两个 Key 是否相同
  · 分别发一次真实请求，打印完整响应头与响应体
  · 针对 401 给出具体判断
"""

import argparse
import sys

import httpx

from core.database import SessionLocal
from core.encryption import decrypt_api_key
from models.models import LLMConfig
from services.llm_client import LLMClient


def fingerprint(label, key):
    """打印 Key 的可诊断特征，不泄露完整内容。"""
    if not key:
        print(f"  {label}: （空）")
        return

    print(f"  {label}:")
    print(f"    长度      {len(key)}")
    print(f"    首 4 位   {key[:4]}")
    print(f"    末 4 位   {key[-4:] if len(key) >= 4 else key}")
    print(f"    前后空白  {'有 ← 会破坏认证' if key != key.strip() else '无'}")
    inner_ws = any(c.isspace() for c in key.strip())
    print(f"    内部空白  {'有 ← Key 被折行或含空格' if inner_ws else '无'}")
    non_ascii = [c for c in key if ord(c) > 127]
    print(f"    非 ASCII  {'有 ' + repr(non_ascii[:3]) + ' ← 含中文标点或全角字符' if non_ascii else '无'}")
    prefix_ok = key.startswith("sk-")
    print(f"    sk- 前缀  {'是' if prefix_ok else '否'}")


def probe(label, client, url, headers, payload, timeout=40):
    """发一次请求并打印完整结果。"""
    print(f"\n── {label} ──")
    print(f"  POST {url}")
    auth = headers.get("Authorization", "")
    print(f"  Authorization: {auth[:14]}...{auth[-4:] if len(auth) > 18 else ''}")

    try:
        r = client.post(url, headers=headers, json=payload, timeout=timeout)
    except Exception as e:
        print(f"  [连接失败] {type(e).__name__}: {e}")
        return False

    print(f"  HTTP {r.status_code}")
    body = r.text.replace("\n", " ")[:400]
    print(f"  响应: {body}")

    if r.status_code == 200:
        try:
            data = r.json()
            if "data" in data and data["data"] and "embedding" in data["data"][0]:
                print(f"  [OK] 向量维度 {len(data['data'][0]['embedding'])}")
            elif "choices" in data:
                print(f"  [OK] 对话返回正常")
        except Exception:
            pass
        return True

    return False


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--key", help="直接测试这个 Key，不读数据库")
    args = parser.parse_args()

    db = SessionLocal()
    try:
        cfg = db.query(LLMConfig).filter(LLMConfig.is_active == True).first()
        if not cfg:
            print("没有激活的 LLM 配置。")
            return 1

        chat_key = decrypt_api_key(cfg.api_key_encrypted)
        emb_key_stored = (
            decrypt_api_key(cfg.embedding_api_key_encrypted)
            if cfg.embedding_api_key_encrypted else None
        )
        info = {
            "name": cfg.name,
            "provider": cfg.provider,
            "api_url": cfg.api_url,
            "chat_model": cfg.chat_model,
            "embedding_model": cfg.embedding_model,
            "embedding_url": cfg.embedding_url,
        }
    finally:
        db.close()

    effective_emb_key = args.key or emb_key_stored or chat_key

    print("=" * 66)
    print("  LLM / Embedding 认证诊断")
    print("=" * 66)
    print(f"  配置名称    {info['name']}")
    print(f"  Provider    {info['provider']}")
    print(f"  对话模型    {info['chat_model']}")
    print(f"  向量模型    {info['embedding_model'] or '（未配置）'}")

    print("\n【端点】")
    print(f"  对话 base   {info['api_url']}")
    print(f"  向量 base   {info['embedding_url'] or '（未填，复用对话 base）'}")

    print("\n【Key 指纹】")
    fingerprint("对话 Key", chat_key)
    if args.key:
        print("\n  向量 Key: （命令行指定）")
        fingerprint("向量 Key", args.key)
    elif emb_key_stored:
        fingerprint("向量 Key", emb_key_stored)
    else:
        print("\n  向量 Key: 未单独配置，复用对话 Key")

    same = effective_emb_key == chat_key
    print(f"\n  两个 Key 是否相同: {'是' if same else '否'}")

    # 构造客户端
    llm = LLMClient(
        provider=info["provider"],
        api_key=chat_key,
        chat_model=info["chat_model"],
        api_url=info["api_url"],
        embedding_model=info["embedding_model"],
        embedding_url=info["embedding_url"],
        embedding_api_key=effective_emb_key,
    )
    client = httpx.Client()

    # ---- 对话 ----
    chat_url = llm._endpoint(info["api_url"], "chat/completions")
    chat_ok = probe(
        "对话接口",
        client,
        chat_url,
        {
            "Authorization": f"Bearer {chat_key.strip()}",
            "Content-Type": "application/json",
        },
        {
            "model": info["chat_model"],
            "messages": [{"role": "user", "content": "回复两个字：正常"}],
            "max_tokens": 20,
        },
    )

    # ---- 向量 ----
    emb_ok = False
    if info["embedding_model"]:
        emb_url = llm._endpoint(info["embedding_url"] or info["api_url"], "embeddings")
        emb_ok = probe(
            "向量接口",
            client,
            emb_url,
            {
                "Authorization": f"Bearer {effective_emb_key.strip()}",
                "Content-Type": "application/json",
            },
            {"model": info["embedding_model"], "input": "测试文本"},
        )
    else:
        print("\n── 向量接口 ──\n  未配置向量模型，跳过")

    client.close()
    llm.close()

    # ---- 结论 ----
    print("\n" + "=" * 66)
    print("  结论")
    print("=" * 66)

    if chat_ok and emb_ok:
        print("  两个接口均正常。")
    elif chat_ok and not emb_ok:
        print("  对话正常，向量 401。可能原因按概率排序：")
        print("    1. 向量端点的 Key 与端点不匹配")
        print("       阿里云百炼的「专属实例」和「公共实例」Key 不通用；")
        print("       腾讯云 TokenHub 的 Token Plan Key 不能调 /v1 按量计费接口")
        print("    2. 向量 Key 复制时带了空格或换行（看上面的「前后空白」）")
        print("    3. 该 Key 没有向量模型的调用权限")
        print("\n  排查：用 --key 指定一个确定可用的 Key 再测：")
        print("    docker exec -it claw-backend python diagnose_key.py --key 'sk-xxx'")
    elif not chat_ok and not emb_ok:
        print("  两个接口都失败，说明 Key 本身无效或站点不匹配。")
        print("    阿里云：确认 Key 与控制台所在站点一致（北京/新加坡）")
        print("    腾讯云：确认 Key 与 Base URL 属于同一站点")
    else:
        print("  对话失败但向量正常，检查对话模型的名称与权限。")

    print("=" * 66)
    return 0


if __name__ == "__main__":
    sys.exit(main())
