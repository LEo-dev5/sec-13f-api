# app/main.py
import os
from fastapi import FastAPI, Request, Response
from contextlib import asynccontextmanager
from fastapi.staticfiles import StaticFiles

# 1. DB 및 모델 임포트
from app.db.database import engine, Base, SessionLocal
from app.db.models import Institution, Holding, Insight, Feedback, VisitLog

# 2. 라우터 임포트 (stock 포함 확인!)
from app.api.v1.endpoints import home, search, sec, insights, feedback, admin, stock

is_production = os.getenv("RENDER") is not None

@asynccontextmanager
async def lifespan(app: FastAPI):
    print("🚀 [System] 서버 부팅 중...")
    try:
        Base.metadata.create_all(bind=engine)
        print("✅ [System] DB 테이블 체크 완료")
    except Exception as e:
        print(f"🔥 [System] DB 에러: {e}")
    yield
    print("👋 [System] 서버 종료")

app = FastAPI(
    title="Easy13F",
    lifespan=lifespan,
    docs_url=None if is_production else "/docs",
    redoc_url=None if is_production else "/redoc"
)

# 방문자 로깅 미들웨어
@app.middleware("http")
async def log_visits(request: Request, call_next):
    response = await call_next(request)
    if not request.url.path.startswith(("/static", "/admin", "/favicon.ico")):
        try:
            forwarded = request.headers.get("X-Forwarded-For")
            client_ip = forwarded.split(",")[0] if forwarded else request.client.host
            db = SessionLocal()
            visit = VisitLog(ip_address=client_ip, path=request.url.path)
            db.add(visit)
            db.commit()
            db.close()
        except: pass
    return response

# 폴더 생성 및 정적 파일 연결
os.makedirs("app/static/uploads", exist_ok=True)
app.mount("/static", StaticFiles(directory="app/static"), name="static")

# 🚨 3. 라우터 등록 (중복 제거 및 순서 정리)
app.include_router(home.router, tags=["Home"])
app.include_router(search.router, tags=["Search"])     # /search, /suggest
app.include_router(stock.router, tags=["Stock"])       # /stock/{ticker} (이제 Not Found 해결됨!)
app.include_router(sec.router, prefix="/api/v1/sec", tags=["SEC"])
app.include_router(insights.router, prefix="/api/v1/insights", tags=["Insights"])
app.include_router(feedback.router, prefix="/api/v1/feedback", tags=["Feedback"])
app.include_router(admin.router, prefix="/admin", tags=["Admin"])