import os
from fastapi import FastAPI, Request
from contextlib import asynccontextmanager
from fastapi.staticfiles import StaticFiles

from app.db.database import engine, Base, SessionLocal
from app.db.models import VisitLog

# 모든 라우터 가져오기
from app.api.v1.endpoints import home, search, sec, insights, feedback, admin, stock

is_production = os.getenv("RENDER") is not None

@asynccontextmanager
async def lifespan(app: FastAPI):
    print("🚀 [System] 서버 부팅 중...")
    try:
        Base.metadata.create_all(bind=engine)
    except: pass
    yield
    print("👋 [System] 서버 종료")

app = FastAPI(lifespan=lifespan, docs_url=None if is_production else "/docs")

# 방문자 로깅
@app.middleware("http")
async def log_visits(request: Request, call_next):
    response = await call_next(request)
    if not request.url.path.startswith(("/static", "/admin", "/favicon")):
        try:
            db = SessionLocal()
            # ... (기존 로깅 로직 있다면 유지, 없으면 생략 가능) ...
            db.close()
        except: pass
    return response

os.makedirs("app/static/uploads", exist_ok=True)
app.mount("/static", StaticFiles(directory="app/static"), name="static")

# 🚨 [라우터 등록 최종 정리]
app.include_router(home.router, tags=["Home"])
# search.py 안에 주소가 /search, /api/v1/search/suggest로 되어있으므로 prefix 없이 등록
app.include_router(search.router, tags=["Search"]) 
app.include_router(stock.router, tags=["Stock"]) # /stock/{ticker}
app.include_router(sec.router, prefix="/api/v1/sec", tags=["SEC"])
app.include_router(insights.router, prefix="/api/v1/insights", tags=["Insights"])
app.include_router(feedback.router, prefix="/api/v1/feedback", tags=["Feedback"])
app.include_router(admin.router, prefix="/admin", tags=["Admin"])