"""轻量级增量迁移。

项目没有引入 Alembic（单人维护、部署环境简单），后续版本新增的列
用「查 information_schema + ALTER TABLE」的方式补齐。

设计要点：
  · 可重复执行，已存在的列直接跳过
  · 只做加列，不做删改，避免误伤数据
  · 在 FastAPI startup 里调用，重启即生效，不需要额外运维动作
"""

from sqlalchemy import text

# (表名, 列名, 列类型定义)
MIGRATIONS = [
    ("kb_documents", "search_tsv", "tsvector"),
    ("llm_configs", "embedding_api_key_encrypted", "TEXT"),
]


def ensure_schema(engine) -> list[str]:
    """补齐缺失的列，返回本次实际新增的字段列表。"""
    applied: list[str] = []

    for table, column, ddl in MIGRATIONS:
        try:
            with engine.begin() as conn:
                exists = conn.execute(text("""
                    SELECT 1 FROM information_schema.columns
                    WHERE table_name = :t AND column_name = :c
                """), {"t": table, "c": column}).first()

                if exists:
                    continue

                conn.execute(text(
                    f"ALTER TABLE {table} ADD COLUMN {column} {ddl}"
                ))
                applied.append(f"{table}.{column}")
        except Exception as e:
            # 表不存在或权限不足时跳过，不阻断服务启动
            print(f"[schema] 补列 {table}.{column} 失败: {e}")

    return applied
