from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from core.config import settings
from core.database import engine, Base
from core.schema_guard import ensure_schema
from api.auth import router as auth_router
from api.llm import router as llm_router
from api.kb import router as kb_router
from api.documents import router as documents_router
from api.search import router as search_router
from api.settings import router as settings_router
from api.stats import router as stats_router
from api.users import router as users_router
from api.websocket import router as ws_router

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="国企公文起草、检索与知识库管理系统",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers
app.include_router(auth_router)
app.include_router(llm_router)
app.include_router(kb_router)
app.include_router(documents_router)
app.include_router(search_router)
app.include_router(settings_router)
app.include_router(stats_router)
app.include_router(users_router)
app.include_router(ws_router)


@app.get("/api/health")
def health():
    return {"status": "ok", "app": settings.APP_NAME, "version": settings.APP_VERSION}


@app.on_event("startup")
def startup():
    # 建表（首次部署）+ 补齐后续版本新增的列（重启即生效）
    Base.metadata.create_all(bind=engine)
    applied = ensure_schema(engine)
    if applied:
        print(f"[startup] 已补齐字段: {', '.join(applied)}")
    ensure_company_kb()


def ensure_company_kb():
    """确保存在公司级知识库。

    公司级知识库对所有账号可见，是「一处上传、全员可用」的载体。
    之前只有 bootstrap.py 会创建，没跑过初始化的部署就一直缺这个库，
    管理员上传的文档全落在个人库里，其他人检索不到。
    """
    from core.database import SessionLocal
    from models.models import KnowledgeBase

    db = SessionLocal()
    try:
        exists = (
            db.query(KnowledgeBase)
            .filter(KnowledgeBase.level == "company")
            .first()
        )
        if exists is None:
            db.add(KnowledgeBase(user_id=None, name="公司制度库", level="company"))
            db.commit()
            print("[startup] 已创建公司级知识库：公司制度库")
    except Exception as e:
        print(f"[startup] 检查公司级知识库失败: {e}")
        db.rollback()
    finally:
        db.close()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
