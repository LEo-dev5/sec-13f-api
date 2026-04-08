import os
from fastapi import FastAPI
from contextlib import asynccontextmanager

from app.db.database import engine, Base
from app.api.v1.endpoints import sec, management

is_production = os.getenv("RENDER") is not None

@asynccontextmanager
async def lifespan(app: FastAPI):
    print("🚀 [System] 13F API 서버 부팅 중...")
    try:
        Base.metadata.create_all(bind=engine)
    except Exception as e:
        print(f"⚠️ DB 초기화 실패: {e}")
    yield
    print("👋 [System] 서버 종료")

app = FastAPI(
    title="13F API Server",
    description="SEC 13F 기관 투자자 포트폴리오 REST API",
    version="1.0.0",
    lifespan=lifespan,
    docs_url=None if is_production else "/docs",
    redoc_url=None if is_production else "/redoc",
)

app.include_router(sec.router, prefix="/api/v1/sec", tags=["13F SEC"])
app.include_router(management.router, prefix="/api/v1/management", tags=["Management"])

@app.get("/health")
async def health_check():
    return {"status": "ok"}
