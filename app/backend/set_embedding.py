#!/usr/bin/env python3
"""
为当前激活的 LLM 配置设置 Embedding 模型与独立地址。

腾讯云 TokenHub 的对话与向量接口不在同一个路径：
    对话  https://tokenhub-intl.tencentcloudmaas.com/plan/v3/chat/completions
    向量  https://tokenhub-intl.tencentcloudmaas.com/v1/embeddings
所以 embedding 地址必须单独指定，不能从对话地址推导。

用法：
    # 按 TokenHub 默认值写入并测试
    docker exec -it claw-backend python set_embedding.py

    # 只测试不写库
    docker exec -it claw-backend python set_embedding.py --test-only

    # 指定其他服务商
    docker exec -it claw-backend python set_embedding.py \
        --model text-embedding-v3 \
        --url https://dashscope.aliyuncs.com/compatible-mode/v1
"""

import argparse
import sys

from core.database import SessionLocal, engine
from core.encryption import decrypt_api_key, encrypt_api_key
from core.schema_guard import ensure_schema
from models.models import LLMConfig
from services.llm_client import LLMClient

REQUIRED_DIM = 1024  # 与 document_chunks.embedding 的 vector(1024) 一致

DEFAULT_MODEL = "kinfra-text-embedding-0.6b"
DEFAULT_URL = "https://tokenhub-intl.tencentcloudmaas.com/v1"


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--model", default=DEFAULT_MODEL, help="向量模型 ID")
    p.add_argument("--url", default=DEFAULT_URL, help="向量接口 base 或完整地址")
    p.add_argument("--key", default=None,
                   help="向量接口专用 API Key。TokenHub 的 Token Plan Key 只能调 "
                        "/plan/v3，调用 /v1 按量计费接口需另一个 Key；留空则复用主 Key")
    p.add_argument("--test-only", action="store_true", help="只测试，不写数据库")
    args = p.parse_args()

    # 脚本可独立运行，先确保数据库结构是最新的
    applied = ensure_schema(engine)
    if applied:
        print(f"[schema] 已补齐字段: {', '.join(applied)}")

    db = SessionLocal()
    try:
        cfg = db.query(LLMConfig).filter(LLMConfig.is_active == True).first()
        if not cfg:
            print("没有激活的 LLM 配置，请先在设置页激活一个。")
            return 1

        api_key = decrypt_api_key(cfg.api_key_encrypted)
        cfg_id, cfg_name = cfg.id, cfg.name

        # 向量 Key 优先级：命令行 > 数据库已存 > 复用主 Key
        if args.key:
            emb_key = args.key
            key_source = "命令行指定"
        elif cfg.embedding_api_key_encrypted:
            emb_key = decrypt_api_key(cfg.embedding_api_key_encrypted)
            key_source = "数据库已存"
        else:
            emb_key = None
            key_source = "复用对话 Key"

        print("=" * 62)
        print("  设置 Embedding")
        print("=" * 62)
        print(f"  配置:       {cfg_name}")
        print(f"  向量模型:   {args.model}")
        print(f"  向量地址:   {args.url}")
        print(f"  向量 Key:   {key_source}")
        print(f"  目标维度:   {REQUIRED_DIM}")

        # 构造客户端并测试
        llm = LLMClient(
            provider=cfg.provider,
            api_key=api_key,
            chat_model=cfg.chat_model,
            api_url=cfg.api_url,
            embedding_model=args.model,
            embedding_url=args.url,
            embedding_api_key=emb_key,
        )

        actual_url = llm._endpoint(args.url, "embeddings")
        print(f"  实际请求:   {actual_url}")
        print("─" * 62)

        try:
            r = llm.embed("采购管理办法测试文本")
        except Exception as e:
            print(f"[FAIL] 调用失败: {e}")
            llm.close()
            return 1

        print(f"[OK]   返回 {r.dim} 维，耗时 {r.latency_ms}ms")

        if r.dim != REQUIRED_DIM:
            print(f"[FAIL] 维度 {r.dim} ≠ 数据库要求的 {REQUIRED_DIM} 维")
            print("       需要改表结构才能使用，请联系我调整。")
            llm.close()
            return 1

        llm.close()

        if args.test_only:
            print("\n--test-only：测试通过，未写入数据库。")
            return 0

        # 写回数据库
        row = db.query(LLMConfig).filter(LLMConfig.id == cfg_id).first()
        row.embedding_model = args.model
        row.embedding_url = args.url
        if args.key:
            row.embedding_api_key_encrypted = encrypt_api_key(args.key)
        db.commit()

        print("\n" + "=" * 62)
        print("  已写入数据库")
        print("=" * 62)
        print("  下一步：")
        print("  1. 重启服务让配置生效")
        print("       docker restart claw-backend claw-worker")
        print("  2. 把知识库里已有的文档重新入库（之前没算向量的要补）")
        print("       在知识库页面点文档的「重试」，或重新上传")
        print("  3. 跑一次自检确认")
        print("       docker exec -it claw-backend python verify.py")
        print("=" * 62)
        return 0

    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
