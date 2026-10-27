#!/usr/bin/env python3
"""
公文辅助系统 — 系统自检

在容器内执行，凭据不出容器：
    docker exec -it gongwen-backend python verify.py

逐项检查数据库、扩展、账号、LLM 连通性、队列、知识库数据，
最后给出「能否投入使用」的结论。
"""

import sys
import traceback

from sqlalchemy import text

from core.config import settings
from core.database import SessionLocal, engine
from core.encryption import decrypt_api_key
from core.schema_guard import ensure_schema
from models.models import (
    User, KnowledgeBase, KBDocument, Document, LLMConfig,
)
from services.llm_client import LLMClient

OK, WARN, FAIL, INFO = "  [OK]  ", "  [WARN]", "  [FAIL]", "  [--]  "
issues = []   # (level, message)


def head(title):
    print(f"\n{'─' * 62}\n{title}\n{'─' * 62}")


def record(level, msg):
    issues.append((level, msg))


# ---------------------------------------------------------------- 1 数据库

def check_database(db):
    head("1. 数据库")
    try:
        ver = db.execute(text("SELECT version()")).scalar()
        print(f"{OK} {ver.split(',')[0]}")
    except Exception as e:
        print(f"{FAIL} 连接失败: {e}")
        record("FAIL", "数据库无法连接")
        return False

    expected = {
        "users", "llm_configs", "knowledge_bases", "kb_documents",
        "document_chunks", "documents", "document_versions",
        "generation_tasks", "word_templates",
    }
    rows = db.execute(text(
        "SELECT tablename FROM pg_tables WHERE schemaname='public'"
    )).fetchall()
    actual = {r[0] for r in rows}
    missing = expected - actual
    if missing:
        print(f"{FAIL} 缺少表: {', '.join(sorted(missing))}")
        record("FAIL", f"缺少数据表: {missing}")
    else:
        print(f"{OK} 9 张业务表齐全")
    return True


# ---------------------------------------------------------------- 2 扩展

def check_extensions(db):
    head("2. 数据库扩展")
    rows = db.execute(text("SELECT extname, extversion FROM pg_extension")).fetchall()
    installed = {r[0]: r[1] for r in rows}

    for name, required in [("vector", True), ("pg_trgm", True), ("zhparser", False)]:
        if name in installed:
            print(f"{OK} {name} {installed[name]}")
        elif required:
            print(f"{FAIL} {name} 未安装（必需）")
            record("FAIL", f"扩展 {name} 缺失")
        else:
            print(f"{WARN} {name} 未安装 → 全文检索降级为 pg_trgm 模糊匹配")
            record("WARN", "zhparser 缺失，检索走 pg_trgm 降级路径")

    # 向量列类型
    row = db.execute(text("""
        SELECT udt_name FROM information_schema.columns
        WHERE table_name='document_chunks' AND column_name='embedding'
    """)).first()
    if row and row[0] == "vector":
        print(f"{OK} document_chunks.embedding 类型 = vector")
    else:
        print(f"{FAIL} document_chunks.embedding 类型 = {row[0] if row else '不存在'}")
        record("FAIL", "向量列类型不正确，语义检索不可用")

    # search_tsv
    row = db.execute(text("""
        SELECT 1 FROM information_schema.columns
        WHERE table_name='kb_documents' AND column_name='search_tsv'
    """)).first()
    print(f"{OK if row else WARN} kb_documents.search_tsv "
          f"{'存在' if row else '不存在（关键词检索仍可用）'}")


# ---------------------------------------------------------------- 3 账号

def check_accounts(db):
    head("3. 账号与知识库")
    users = db.query(User).all()
    admins = [u for u in users if u.role == "admin"]
    print(f"{INFO} 账号总数 {len(users)}，管理员 {len(admins)}")
    for u in users:
        flag = "admin" if u.role == "admin" else "user"
        label = u.display_name or u.username
        state = "" if getattr(u, "is_active", True) else " [已停用]"
        print(f"        - {label} ({u.username}, {flag}) {u.department or ''}{state}")

    if not admins:
        print(f"{FAIL} 没有管理员账号，无法上传公司级管理办法")
        record("FAIL", "缺少管理员账号")

    company = db.query(KnowledgeBase).filter(KnowledgeBase.level == "company").all()
    if company:
        for kb in company:
            print(f"{OK} 公司级知识库: {kb.name}")
    else:
        print(f"{FAIL} 公司级知识库不存在")
        record("FAIL", "公司级知识库缺失，需重跑 bootstrap.py")

    personal = db.query(KnowledgeBase).filter(KnowledgeBase.level == "personal").all()
    print(f"{INFO} 个人知识库 {len(personal)} 个")


# ---------------------------------------------------------------- 4 LLM

def check_llm(db):
    head("4. LLM 配置与连通性")
    configs = db.query(LLMConfig).all()
    if not configs:
        print(f"{FAIL} 未配置任何 LLM")
        record("FAIL", "没有 LLM 配置，生成和检索都不可用")
        return

    for c in configs:
        mark = "★激活" if c.is_active else "  未激活"
        emb = c.embedding_model or "（无）"
        print(f"{INFO} {mark} {c.name} | {c.provider} | chat={c.chat_model} | emb={emb}")

    active = next((c for c in configs if c.is_active), None)
    if not active:
        print(f"{FAIL} 没有激活的配置，生成时会报 No active LLM config")
        record("FAIL", "LLM 配置未激活")
        return

    print(f"\n{INFO} 正在用「{active.name}」做真实调用测试…")
    try:
        llm = LLMClient(
            provider=active.provider,
            api_key=decrypt_api_key(active.api_key_encrypted),
            chat_model=active.chat_model,
            api_url=active.api_url,
            embedding_model=active.embedding_model,
            embedding_url=active.embedding_url,
            embedding_api_key=(
                decrypt_api_key(active.embedding_api_key_encrypted)
                if active.embedding_api_key_encrypted else None
            ),
        )
    except Exception as e:
        print(f"{FAIL} 客户端初始化失败: {e}")
        record("FAIL", f"LLM 客户端初始化失败: {e}")
        return

    # chat
    try:
        r = llm.chat(
            [{"role": "user", "content": "回复两个字：正常"}],
            max_tokens=32,
        )
        text = r.content.strip()
        if text:
            print(f"{OK} 对话接口 {r.latency_ms}ms → {text[:40]}")
        else:
            # 部分模型（如带思考模式的 DeepSeek V4）在 max_tokens 过小时
            # 把额度全用在推理上，content 会是空的
            print(f"{WARN} 对话接口 {r.latency_ms}ms 返回空内容")
            print(f"       可能原因：max_tokens 太小被推理过程占满，"
                  f"或该模型不支持此调用方式")
            record("WARN", "对话接口返回空内容，生成可能拿不到正文")
    except Exception as e:
        print(f"{FAIL} 对话接口失败: {e}")
        record("FAIL", f"对话接口不可用: {str(e)[:150]}")

    # embedding
    if active.embedding_model:
        try:
            r = llm.embed("测试文本")
            if r.dim == 1024:
                print(f"{OK} 向量接口 {r.latency_ms}ms → {r.dim} 维")
            else:
                print(f"{WARN} 向量接口 {r.latency_ms}ms → {r.dim} 维"
                      f"（数据库要求 1024 维，语义检索将不可用）")
                record("WARN", f"Embedding 维度 {r.dim} ≠ 1024")
        except Exception as e:
            print(f"{WARN} 向量接口不可用: {str(e)[:150]}")
            print(f"        → 生成和检索降级为关键词匹配，功能可用")
            record("WARN", "Embedding 不可用，仅关键词检索")
    else:
        print(f"{WARN} 未配置 Embedding 模型 → 检索走关键词匹配")
        record("WARN", "未配置 Embedding，仅关键词检索")

    llm.close()


# ---------------------------------------------------------------- 5 队列

def check_queue():
    head("5. Redis 与异步任务")
    try:
        import redis
        r = redis.from_url(settings.REDIS_URL)
        r.ping()
        print(f"{OK} Redis 连接正常")
    except Exception as e:
        print(f"{FAIL} Redis 连接失败: {e}")
        record("FAIL", "Redis 不可用，文档生成和文件解析会失败")
        return

    try:
        from tasks.celery_app import celery_app
        replies = celery_app.control.ping(timeout=3)
        if not replies:
            print(f"{FAIL} 没有 Celery worker 响应")
            record("FAIL", "Celery worker 未运行，检查 docker logs gongwen-worker")
            return

        print(f"{OK} Celery worker 在线 {len(replies)} 个")

        # 检查 worker 实际注册了哪些业务任务。
        # 只 ping 通不代表任务可用：tasks/tasks.py 没被 import 时
        # worker 能响应 ping，但 [tasks] 列表为空，收到任务会报 unregistered，
        # 表现为「点了生成没反应」，日志里只有一行 ERROR。
        inspector = celery_app.control.inspect(timeout=3)
        registered = inspector.registered() or {}
        all_tasks = set()
        for task_list in registered.values():
            all_tasks.update(task_list)

        expected = {
            "generate_document": "文档生成",
            "process_kb_document": "知识库文件解析",
        }
        missing = [
            label for needle, label in expected.items()
            if not any(needle in t for t in all_tasks)
        ]

        if missing:
            print(f"{FAIL} worker 未注册任务: {', '.join(missing)}")
            print(f"       生成和解析会静默失败。检查 tasks/celery_app.py 的 include 配置")
            record("FAIL", f"Celery 未注册任务: {', '.join(missing)}")
        else:
            print(f"{OK} 业务任务已注册（{len(all_tasks)} 个任务）")
    except Exception as e:
        print(f"{WARN} worker 探测失败: {str(e)[:100]}")


# ---------------------------------------------------------------- 6 数据

def check_data(db):
    head("6. 知识库与文档数据")
    doc_count = db.query(KBDocument).count()
    chunk_total = db.execute(text("SELECT COUNT(*) FROM document_chunks")).scalar() or 0
    chunk_vec = db.execute(
        text("SELECT COUNT(*) FROM document_chunks WHERE embedding IS NOT NULL")
    ).scalar() or 0

    print(f"{INFO} 知识库文档 {doc_count} 份，分块 {chunk_total} 个，"
          f"其中 {chunk_vec} 个有向量")

    if doc_count == 0:
        print(f"{WARN} 知识库为空 → 生成时没有制度依据可引用，建议先上传管理办法")
        record("WARN", "知识库为空，生成内容将缺乏制度依据")

    status_rows = db.execute(text(
        "SELECT status, COUNT(*) FROM kb_documents GROUP BY status"
    )).fetchall()
    for st, cnt in status_rows:
        icon = OK if st == "done" else (FAIL if st == "failed" else WARN)
        print(f"{icon} 文档状态 {st}: {cnt}")

    generated = db.query(Document).count()
    done = db.query(Document).filter(Document.status == "done").count()
    print(f"{INFO} 公文 {generated} 篇，已完成 {done} 篇")


# ---------------------------------------------------------------- 主流程

def main():
    print("=" * 62)
    print("  公文辅助系统 — 系统自检")
    print(f"  {settings.APP_NAME} v{settings.APP_VERSION}")
    print("=" * 62)

    db = SessionLocal()
    try:
        # 脚本可独立运行，先确保数据库结构是最新的
        applied = ensure_schema(engine)
        if applied:
            print(f"[schema] 已补齐字段: {', '.join(applied)}")

        if not check_database(db):
            return 1
        check_extensions(db)
        check_accounts(db)
        check_llm(db)
        check_queue()
        check_data(db)
    except Exception:
        print("\n自检过程异常：")
        traceback.print_exc()
        return 1
    finally:
        db.close()

    # 结论
    head("结论")
    fails = [m for lv, m in issues if lv == "FAIL"]
    warns = [m for lv, m in issues if lv == "WARN"]

    if fails:
        print(f"{FAIL} 存在 {len(fails)} 项阻塞问题：")
        for m in fails:
            print(f"        · {m}")
        print("\n  系统尚不可用，需先解决上述问题。")
    elif warns:
        print(f"{OK} 核心链路可用，有 {len(warns)} 项非阻塞提示：")
        for m in warns:
            print(f"        · {m}")
        print("\n  可以开始使用。建议先上传管理办法，再新建公文。")
    else:
        print(f"{OK} 全部检查通过，系统可正常使用。")

    print("=" * 62)
    return 0 if not fails else 1


if __name__ == "__main__":
    sys.exit(main())
