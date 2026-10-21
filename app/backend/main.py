from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from core.config import settings
from core.database import engine, Base
from api.auth import router as auth_router
from api.llm import router as llm_router
from api.kb import router as kb_router
from api.documents import router as documents_router
from api.search import router as search_router
from api.websocket import router as ws_router

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="国企请示材料自动生成、检索与知识库管理系统",
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
app.include_router(ws_router)


@app.get("/api/health")
def health():
    return {"status": "ok", "app": settings.APP_NAME, "version": settings.APP_VERSION}


@app.on_event("startup")
def startup():
    # Create tables (in production, use Alembic migrations)
    Base.metadata.create_all(bind=engine)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
