#!/usr/bin/env python3
"""
天府数产公文辅助系统 — 部署后初始化脚本

功能：
  1. 修复数据库结构（补齐 search_tsv 列、向量列类型、索引、触发器）
  2. 创建/重置管理员账号
  3. 创建公司级知识库（用于存放统一上传的管理办法）

用法（在服务器上，项目目录内执行）：

  # 默认创建 admin / Admin@2026
  docker exec -it claw-backend python bootstrap.py

  # 自定义账号密码
  docker exec -it claw-backend python bootstrap.py --username taoye --password 'MyPass@2026'

  # 只修复数据库结构，不动账号
  docker exec -it claw-backend python bootstrap.py --fix-schema-only

  # 查看当前已有账号
  docker exec -it claw-backend python bootstrap.py --list-users

脚本是幂等的，重复执行不会出错。
"""

import argparse
import sys

from sqlalchemy import text
from core.database import engine, SessionLocal, Base
from core.security import hash_password
from models.models import User, KnowledgeBase


# ---------------------------------------------------------------- helpers

def run_sql(db, sql, label, critical=False):
    """执行单条 DDL，失败不中断（除非 critical=True）。"""
    try:
        db.execute(text(sql))
        db.commit()
        print(f"  [OK]   {label}")
        return True
    except Exception as e:
        db.rollback()
        msg = str(e).split("\n")[0][:120]
        if critical:
            print(f"  [FAIL] {label}: {msg}")
        else:
            print(f"  [SKIP] {label}: {msg}")
        return False


# ---------------------------------------------------------------- schema

def ensure_tables():
    """确保所有表已创建（等价于 FastAPI startup 的 create_all）。"""
    print("\n[1/4] 检查数据表")
    try:
        Base.metadata.create_all(bind=engine)
        print("  [OK]   数据表已就绪")
        return True
    except Exception as e:
        print(f"  [FAIL] 建表失败: {e}")
        return False


def fix_schema(db):
    """幂等修复数据库结构。zhparser 缺失时自动降级到 pg_trgm。"""
    print("\n[2/4] 修复数据库结构")

    # --- 扩展 ---
    run_sql(db, "CREATE EXTENSION IF NOT EXISTS vector", "扩展 pgvector")
    run_sql(db, "CREATE EXTENSION IF NOT EXISTS pg_trgm", "扩展 pg_trgm")

    zhparser_ok = run_sql(
        db, "CREATE EXTENSION IF NOT EXISTS zhparser", "扩展 zhparser（可选）"
    )

    # --- 中文全文检索配置 ---
    if zhparser_ok:
        run_sql(db, """
            DO $$
            BEGIN
                IF NOT EXISTS (SELECT 1 FROM pg_ts_config WHERE cfgname = 'chinese_zh') THEN
                    CREATE TEXT SEARCH CONFIGURATION chinese_zh (PARSER = zhparser);
                    ALTER TEXT SEARCH CONFIGURATION chinese_zh
                        ADD MAPPING FOR n,v,a,i,e,l WITH simple;
                END IF;
            END $$;
        """, "全文检索配置 chinese_zh")
    else:
        print("  [INFO] zhparser 不可用，全文检索将降级为 pg_trgm 模糊匹配")

    # --- search_tsv 列与索引 ---
    run_sql(db,
            "ALTER TABLE kb_documents ADD COLUMN IF NOT EXISTS search_tsv tsvector",
            "字段 kb_documents.search_tsv")

    # --- LLM 配置：向量接口独立 Key ---
    run_sql(db,
            "ALTER TABLE llm_configs "
            "ADD COLUMN IF NOT EXISTS embedding_api_key_encrypted TEXT",
            "字段 llm_configs.embedding_api_key_encrypted")

    run_sql(db, """
        CREATE INDEX IF NOT EXISTS idx_kb_documents_search_tsv
            ON kb_documents USING GIN(search_tsv)
    """, "索引 kb_documents.search_tsv")

    # --- tsvector 自动更新触发器（仅 zhparser 可用时）---
    if zhparser_ok:
        run_sql(db, """
            CREATE OR REPLACE FUNCTION update_kb_search_tsv() RETURNS trigger AS $$
            BEGIN
                NEW.search_tsv := to_tsvector(
                    'chinese_zh',
                    coalesce(NEW.title, '') || ' ' || coalesce(NEW.content, '')
                );
                RETURN NEW;
            END;
            $$ LANGUAGE plpgsql
        """, "函数 update_kb_search_tsv")

        run_sql(db, "DROP TRIGGER IF EXISTS trg_kb_documents_search_tsv ON kb_documents",
                "清理旧触发器")
        run_sql(db, """
            CREATE TRIGGER trg_kb_documents_search_tsv
                BEFORE INSERT OR UPDATE ON kb_documents
                FOR EACH ROW EXECUTE FUNCTION update_kb_search_tsv()
        """, "触发器 trg_kb_documents_search_tsv")

    # --- embedding 列转为 vector 类型 ---
    run_sql(db, """
        DO $$
        DECLARE col_type text;
        BEGIN
            SELECT data_type INTO col_type
              FROM information_schema.columns
             WHERE table_name = 'document_chunks' AND column_name = 'embedding';

            IF col_type IS NULL THEN
                ALTER TABLE document_chunks ADD COLUMN embedding vector(1024);
            ELSIF col_type = 'text' THEN
                BEGIN
                    ALTER TABLE document_chunks
                        ALTER COLUMN embedding TYPE vector(1024)
                        USING CASE WHEN embedding IS NULL OR embedding = ''
                                   THEN NULL ELSE embedding::vector END;
                EXCEPTION WHEN others THEN
                    -- 已有数据无法转换时，清空重建
                    ALTER TABLE document_chunks DROP COLUMN embedding;
                    ALTER TABLE document_chunks ADD COLUMN embedding vector(1024);
                END;
            END IF;
        END $$;
    """, "字段 document_chunks.embedding 转 vector(1024)")

    # --- 向量索引 ---
    run_sql(db, """
        CREATE INDEX IF NOT EXISTS idx_document_chunks_embedding
            ON document_chunks USING ivfflat (embedding vector_cosine_ops)
            WITH (lists = 100)
    """, "向量索引 ivfflat")

    # --- trigram 索引（中文模糊检索兜底）---
    run_sql(db, """
        CREATE INDEX IF NOT EXISTS idx_kb_documents_title_trgm
            ON kb_documents USING GIN (title gin_trgm_ops)
    """, "trigram 索引 kb_documents.title")
    run_sql(db, """
        CREATE INDEX IF NOT EXISTS idx_kb_documents_content_trgm
            ON kb_documents USING GIN (content gin_trgm_ops)
    """, "trigram 索引 kb_documents.content")


# ---------------------------------------------------------------- accounts

def create_admin(db, username, password, department=None, reset_password=False):
    """创建或提升管理员账号。

    账号已存在时默认不改密码，避免重跑脚本把用户改过的密码重置回默认值；
    需要重置时显式传 reset_password=True。
    """
    print(f"\n[3/4] 管理员账号: {username}")

    # 先算哈希，失败时给出明确指引（常见于 bcrypt 版本不兼容）
    try:
        pwd_hash = hash_password(password)
    except Exception as e:
        print(f"  [FAIL] 密码哈希失败: {e}")
        print("         常见原因：bcrypt 库缺失或与 passlib 版本冲突")
        print("         修复：docker exec -it claw-backend pip install 'bcrypt==4.2.0'")
        return None

    existing = db.query(User).filter(User.username == username).first()
    if existing:
        if reset_password:
            existing.password_hash = pwd_hash
            print(f"  [OK]   已重置密码")
        else:
            print(f"  [OK]   账号已存在，保留原密码（如需重置加 --reset-password）")
        if existing.role != "admin":
            existing.role = "admin"
            print(f"  [OK]   已提升为 admin")
        if department and not existing.department:
            existing.department = department
        db.commit()
        return existing

    user = User(
        username=username,
        password_hash=pwd_hash,
        role="admin",
        department=department,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    print(f"  [OK]   已创建管理员账号")
    return user


def ensure_personal_kb(db, user):
    """确保管理员有个人知识库。"""
    kb = db.query(KnowledgeBase).filter(
        KnowledgeBase.user_id == user.id,
        KnowledgeBase.level == "personal",
    ).first()
    if kb:
        print(f"  [OK]   个人知识库已存在: {kb.name}")
        return kb
    kb = KnowledgeBase(user_id=user.id, name=f"{user.username}的个人库", level="personal")
    db.add(kb)
    db.commit()
    print(f"  [OK]   已创建个人知识库: {kb.name}")
    return kb


def ensure_company_kb(db):
    """确保公司级知识库存在（所有用户可读，admin 可写）。"""
    print("\n[4/4] 公司级知识库")

    kb = db.query(KnowledgeBase).filter(KnowledgeBase.level == "company").first()
    if kb:
        print(f"  [OK]   已存在: {kb.name}")
        return kb

    kb = KnowledgeBase(
        user_id=None,
        name="公司管理办法库",
        level="company",
    )
    db.add(kb)
    db.commit()
    db.refresh(kb)
    print(f"  [OK]   已创建: {kb.name}")
    return kb


# ---------------------------------------------------------------- misc

def list_users(db):
    print("\n当前账号列表：")
    print(f"  {'用户名':<20} {'角色':<10} {'部门':<20} 创建时间")
    print("  " + "-" * 70)
    users = db.query(User).order_by(User.created_at).all()
    if not users:
        print("  （暂无账号）")
    for u in users:
        dept = u.department or "-"
        created = u.created_at.strftime("%Y-%m-%d %H:%M") if u.created_at else "-"
        print(f"  {u.username:<20} {u.role:<10} {dept:<20} {created}")


# ---------------------------------------------------------------- main

def main():
    parser = argparse.ArgumentParser(description="天府数产公文辅助系统 — 初始化脚本")
    parser.add_argument("--username", default="admin", help="管理员用户名（默认 admin）")
    parser.add_argument("--password", default="Admin@2026", help="管理员密码（默认 Admin@2026）")
    parser.add_argument("--department", default="系统管理", help="部门")
    parser.add_argument("--fix-schema-only", action="store_true", help="只修复数据库结构")
    parser.add_argument("--reset-password", action="store_true",
                        help="账号已存在时强制重置密码（默认保留原密码）")
    parser.add_argument("--list-users", action="store_true", help="列出已有账号")
    args = parser.parse_args()

    print("=" * 64)
    print("  天府数产公文辅助系统 — 部署后初始化")
    print("=" * 64)

    db = SessionLocal()
    try:
        if args.list_users:
            list_users(db)
            return 0

        if not ensure_tables():
            print("\n建表失败，请检查数据库连接。")
            return 1

        fix_schema(db)

        if args.fix_schema_only:
            print("\n仅修复数据库结构，已跳过账号创建。")
            print("=" * 64)
            return 0

        user = create_admin(db, args.username, args.password, args.department,
                            reset_password=args.reset_password)
        if user is None:
            print("\n账号创建失败，已中止。数据库结构修复部分仍然生效。")
            print("=" * 64)
            return 1

        ensure_personal_kb(db, user)
        kb = ensure_company_kb(db)

        print("\n" + "=" * 64)
        print("  初始化完成")
        print("=" * 64)
        print(f"  登录地址: http://<服务器IP>:8081")
        print(f"  用户名:   {args.username}")
        print(f"  密码:     {args.password}")
        print(f"  角色:     admin（可上传公司级管理办法）")
        print(f"  公司库:   {kb.name}")
        print("=" * 64)
        print("\n下一步：登录后进入「设置」配置 LLM API Key，否则无法生成和检索。\n")
        return 0

    except Exception as e:
        print(f"\n初始化失败: {e}")
        import traceback
        traceback.print_exc()
        return 1
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
