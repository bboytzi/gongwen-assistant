#!/usr/bin/env python3
"""
交互式配置 LLM，自动创建配置、测试、激活。

用法：
    docker exec -it claw-backend python setup_llm.py
    docker exec -it claw-backend python setup_llm.py --preset aliyun

脚本会：
  1. 让你选择服务商（或直接指定）
  2. 提示输入 API Key（不回显）
  3. 真实调用对话与向量接口验证
  4. 通过后写入数据库并设为激活（同名的旧配置会被覆盖）
"""

import argparse
import getpass
import sys

from core.database import SessionLocal, engine
from core.encryption import encrypt_api_key
from core.schema_guard import ensure_schema
from models.models import LLMConfig, User
from services.llm_client import LLMClient

# 预设：都是实测可用的组合
PRESETS = {
    "aliyun": {
        "label": "阿里云百炼（推荐，一个 Key 通吃对话+向量）",
        "provider": "qwen",
        "name": "阿里云百炼",
        "api_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "chat_model": "qwen-plus",
        "embedding_model": "text-embedding-v4",
        "embedding_url": None,
    },
    "tokenhub": {
        "label": "腾讯云 TokenHub（向量需单独的 Key）",
        "provider": "tokenhub",
        "name": "腾讯云 TokenHub",
        "api_url": "https://tokenhub-intl.tencentcloudmaas.com/plan/v3",
        "chat_model": "deepseek/deepseek-flash",
        "embedding_model": "kinfra-text-embedding-0.6b",
        "embedding_url": "https://tokenhub-intl.tencentcloudmaas.com/v1",
    },
    "deepseek": {
        "label": "DeepSeek 官方（无向量能力）",
        "provider": "deepseek",
        "name": "DeepSeek",
        "api_url": "https://api.deepseek.com/v1",
        "chat_model": "deepseek-chat",
        "embedding_model": None,
        "embedding_url": None,
    },
}

REQUIRED_DIM = 1024


def pick_preset(explicit: str | None) -> str:
    if explicit:
        if explicit not in PRESETS:
            print(f"未知预设 {explicit}，可选：{', '.join(PRESETS)}")
            sys.exit(1)
        return explicit

    print("\n选择服务商：")
    keys = list(PRESETS)
    for i, k in enumerate(keys, 1):
        print(f"  {i}. {PRESETS[k]['label']}")

    while True:
        raw = input(f"\n输入序号 [1-{len(keys)}，默认 1]: ").strip() or "1"
        if raw.isdigit() and 1 <= int(raw) <= len(keys):
            return keys[int(raw) - 1]
        print("  输入无效，请重试")


def read_key() -> str:
    """优先用 getpass 隐藏输入；无 tty 时回退到普通 input。"""
    try:
        key = getpass.getpass("\n粘贴 API Key（输入时不显示）: ").strip()
    except Exception:
        key = input("\n粘贴 API Key: ").strip()

    if not key:
        print("Key 为空，退出。")
        sys.exit(1)

    # 常见问题自检
    if key != key.strip():
        print("  [注意] Key 首尾有空白，已自动去除")
    if any(c.isspace() for c in key):
        print("  [警告] Key 内部含空白字符，可能复制时折行了")
    if not key.startswith("sk-"):
        print(f"  [提示] Key 不以 sk- 开头（当前开头：{key[:4]}），确认没复制错")

    return key


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--preset", help=f"直接指定预设：{', '.join(PRESETS)}")
    parser.add_argument("--key", help="直接传 Key（会留在 shell 历史里，不建议）")
    args = parser.parse_args()

    applied = ensure_schema(engine)
    if applied:
        print(f"[schema] 已补齐字段: {', '.join(applied)}")

    print("=" * 62)
    print("  LLM 配置向导")
    print("=" * 62)

    preset_key = pick_preset(args.preset)
    preset = PRESETS[preset_key]

    print(f"\n服务商:   {preset['label']}")
    print(f"对话:     {preset['api_url']}  →  {preset['chat_model']}")
    if preset["embedding_model"]:
        emb_base = preset["embedding_url"] or preset["api_url"]
        print(f"向量:     {emb_base}  →  {preset['embedding_model']}")
    else:
        print("向量:     未配置（将只支持关键词检索）")

    api_key = args.key.strip() if args.key else read_key()

    # ---- 测试 ----
    print("\n" + "─" * 62)
    print("测试连通性…")
    print("─" * 62)

    llm = LLMClient(
        provider=preset["provider"],
        api_key=api_key,
        chat_model=preset["chat_model"],
        api_url=preset["api_url"],
        embedding_model=preset["embedding_model"],
        embedding_url=preset["embedding_url"],
    )

    chat_ok = False
    try:
        r = llm.chat(
            [{"role": "user", "content": "回复两个字：正常"}],
            max_tokens=32,
        )
        text = r.content.strip() or "（空响应）"
        print(f"[OK]   对话  {r.latency_ms}ms → {text[:30]}")
        chat_ok = True
    except Exception as e:
        print(f"[FAIL] 对话  {str(e)[:200]}")

    emb_ok = False
    emb_dim = None
    if preset["embedding_model"]:
        try:
            r = llm.embed("测试文本")
            emb_dim = r.dim
            print(f"[OK]   向量  {r.latency_ms}ms → {r.dim} 维")
            emb_ok = r.dim == REQUIRED_DIM
            if not emb_ok:
                print(f"[WARN] 维度 {r.dim} ≠ 数据库要求的 {REQUIRED_DIM}，"
                      f"向量化会被跳过")
        except Exception as e:
            print(f"[FAIL] 向量  {str(e)[:200]}")
    llm.close()

    if not chat_ok:
        print("\n对话接口不通，配置未保存。请检查 Key 和网络后重试。")
        return 1

    # ---- 写库 ----
    db = SessionLocal()
    try:
        owner = db.query(User).filter(User.role == "admin").first()
        if not owner:
            print("\n没有 admin 账号，请先跑 bootstrap.py。")
            return 1

        cfg = db.query(LLMConfig).filter(
            LLMConfig.user_id == owner.id,
            LLMConfig.name == preset["name"],
        ).first()

        if cfg:
            print(f"\n更新已有配置「{preset['name']}」")
        else:
            cfg = LLMConfig(user_id=owner.id, name=preset["name"])
            db.add(cfg)
            print(f"\n创建新配置「{preset['name']}」")

        cfg.provider = preset["provider"]
        cfg.api_url = preset["api_url"]
        cfg.api_key_encrypted = encrypt_api_key(api_key)
        cfg.chat_model = preset["chat_model"]
        cfg.embedding_model = preset["embedding_model"]
        cfg.embedding_url = preset["embedding_url"]

        # 只保留这一个激活配置
        db.query(LLMConfig).filter(LLMConfig.user_id == owner.id).update(
            {"is_active": False}
        )
        cfg.is_active = True
        db.commit()

        print(f"[OK]   已保存并激活")
    finally:
        db.close()

    print("\n" + "=" * 62)
    print("  完成")
    print("=" * 62)
    if emb_ok:
        print("  对话与向量均可用。")
        print("\n  下一步：进「知识库」上传管理办法，上传后状态会走")
        print("  待处理 → 解析中 → 索引中 → 已索引。")
    elif emb_dim:
        print(f"  对话可用，但向量维度 {emb_dim} 不匹配，仅关键词检索。")
    else:
        print("  对话可用，向量不可用，检索走关键词匹配。")
        print("  生成功能不受影响，但引用准确度会下降。")
    print("=" * 62)
    return 0


if __name__ == "__main__":
    sys.exit(main())
