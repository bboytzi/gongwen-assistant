#!/usr/bin/env python3
"""
探测当前 LLM 服务可用的 Embedding 模型与向量维度。

在容器内执行（复用已激活配置里的 API Key，无需重新输入）：
    docker exec -it gongwen-backend python probe_embedding.py

    # 也可以直接指定模型名测试
    docker exec -it gongwen-backend python probe_embedding.py --model xxx

脚本会：
  1. 尝试拉取模型列表（GET {base}/models）
  2. 筛出名字像 embedding 的模型
  3. 逐个调用 /embeddings，打印返回维度
  4. 标出哪些是 1024 维（与当前数据库一致）
"""

import argparse
import sys

import httpx

from core.database import SessionLocal
from core.encryption import decrypt_api_key
from models.models import LLMConfig

# 与 document_chunks.embedding 的 vector(1024) 保持一致
REQUIRED_DIM = 1024

# 常见向量模型名，作为模型列表拉不到时的兜底候选
FALLBACK_CANDIDATES = [
    "kinfra-text-embedding-0.6b",
    "bge-m3",
    "BAAI/bge-m3",
    "bge-large-zh",
    "text-embedding-v3",
    "text-embedding-v2",
]

EMBED_HINTS = ("embed", "bge", "vector", "vec", "m3")


def derive_base(api_url: str) -> str:
    """从 API 地址推导出不含 endpoint 的 base。"""
    url = (api_url or "").rstrip("/")
    for suffix in ("/chat/completions", "/embeddings", "/embedding"):
        if url.endswith(suffix):
            return url[: -len(suffix)]
    return url


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", help="直接测试指定模型名")
    args = parser.parse_args()

    db = SessionLocal()
    try:
        cfg = db.query(LLMConfig).filter(LLMConfig.is_active == True).first()
        if not cfg:
            print("没有激活的 LLM 配置。请先在设置页激活一个配置。")
            return 1

        api_key = decrypt_api_key(cfg.api_key_encrypted)
        base = derive_base(cfg.api_url)
        cfg_name = cfg.name
        cfg_provider = cfg.provider
        if not base:
            print("当前配置没有填写 API 地址，无法探测。")
            return 1
    finally:
        db.close()

    print("=" * 62)
    print("  Embedding 模型探测")
    print("=" * 62)
    print(f"  配置:     {cfg_name} ({cfg_provider})")
    print(f"  API base: {base}")
    print(f"  目标维度: {REQUIRED_DIM}")
    print("=" * 62)

    headers = {"Authorization": f"Bearer {api_key}"}
    client = httpx.Client(timeout=40)

    # ---------- 1. 尝试列出模型 ----------
    models = []
    for path in ("/models", "/model/list", "/models/list"):
        try:
            r = client.get(f"{base}{path}", headers=headers)
            if r.status_code == 200:
                data = r.json()
                items = data.get("data") or data.get("models") or data.get("result") or []
                if isinstance(items, dict):
                    items = items.get("data") or items.get("list") or []
                for it in items:
                    mid = it.get("id") or it.get("model") or it.get("name") if isinstance(it, dict) else str(it)
                    if mid:
                        models.append(str(mid))
                print(f"\n[模型列表] GET {base}{path} → 成功，{len(models)} 个模型")
                break
            else:
                print(f"\n[模型列表] GET {base}{path} → {r.status_code}")
        except Exception as e:
            print(f"\n[模型列表] GET {base}{path} → {type(e).__name__}")

    if models:
        print("\n全部模型：")
        for m in models:
            print(f"    {m}")

    # ---------- 2. 选定候选 ----------
    if args.model:
        candidates = [args.model]
    else:
        candidates = [m for m in models if any(h in m.lower() for h in EMBED_HINTS)]
        if not candidates:
            print("\n模型列表里没识别出 embedding 模型，改用常见候选名试探：")
            candidates = FALLBACK_CANDIDATES
        else:
            print(f"\n筛出 {len(candidates)} 个疑似向量模型。")

    # ---------- 3. 逐个测试 ----------
    print("\n" + "─" * 62)
    print("测试 /embeddings")
    print("─" * 62)

    usable = []
    for model in candidates:
        url = f"{base}/embeddings"
        try:
            r = client.post(
                url,
                headers={**headers, "Content-Type": "application/json"},
                json={"model": model, "input": "采购管理办法测试文本"},
            )
        except Exception as e:
            print(f"  [ERR ]  {model:<40} 连接失败: {type(e).__name__}")
            continue

        if r.status_code != 200:
            snippet = r.text.replace("\n", " ")[:110]
            print(f"  [FAIL]  {model:<40} HTTP {r.status_code}  {snippet}")
            continue

        try:
            vec = r.json()["data"][0]["embedding"]
        except Exception:
            print(f"  [FAIL]  {model:<40} 响应结构异常")
            continue

        dim = len(vec)
        if dim == REQUIRED_DIM:
            print(f"  [可用]  {model:<40} {dim} 维  ← 可直接用于本系统")
            usable.append(model)
        else:
            print(f"  [维度]  {model:<40} {dim} 维  ← 与数据库 {REQUIRED_DIM} 维不符")

    # ---------- 4. 结论 ----------
    print("\n" + "=" * 62)
    if usable:
        print("  结论：找到可用模型")
        print(f"  在设置页把「Embedding 模型」填成：{usable[0]}")
        print("  「Embedding 地址」留空即可，会自动使用同一个 base。")
    elif candidates:
        print("  结论：候选模型均不可用或维度不符")
        print("  · 维度不符时，系统会跳过向量化，检索降级为关键词匹配")
        print("  · 可换一个有 1024 维向量模型的服务商，或告诉我实际维度，我改表结构适配")
    else:
        print("  结论：没有可测试的候选模型")
        print("  请到 TokenHub 控制台的「模型广场 → 向量模型」查看准确的模型 ID，")
        print("  然后用 --model 参数单独测试：")
        print("    docker exec -it gongwen-backend python probe_embedding.py --model <模型ID>")
    print("=" * 62)

    client.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
