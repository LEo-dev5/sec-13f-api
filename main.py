# app/main.py
import os  # 👈 1. os 모듈 추가
from fastapi import FastAPI
from contextlib import asynccontextmanager
from fastapi.staticfiles import StaticFiles

# 라우터 파일들 임포트
from app.api.v1.endpoints import sec, admin, home, search, stock, insights, feedback
from app.services.ticker_service import load_sec_tickers

# 2. 수명 주기 설정
@asynccontextmanager
async def lifespan(app: FastAPI):
    print("🚀 [System] 서버 시작: 티커 데이터 로딩 중...")
    # (옵션) 배포 환경에서는 티커 로딩이 오래 걸리면 타임아웃 날 수 있으므로
    # 필요하다면 try-except로 감싸거나 비동기로 뺄 수 있습니다.
    try:
        await load_sec_tickers()
    except Exception as e:
        print(f"⚠️ 티커 로딩 실패 (일시적일 수 있음): {e}")
    yield
    print("👋 [System] 서버 종료")

app = FastAPI(lifespan=lifespan)

# 🚨 [핵심 수정] 폴더가 없으면 강제로 만듭니다!
# Render 서버에는 이 폴더들이 없을 수 있기 때문입니다.
os.makedirs("app/static/uploads", exist_ok=True)

# 3. 정적 파일 연결
app.mount("/static", StaticFiles(directory="app/static"), name="static")

# 4. 라우터 등록
app.include_router(home.router, tags=["Home"])
app.include_router(sec.router, prefix="/api/v1/sec", tags=["SEC"])
app.include_router(search.router, tags=["Search"])
app.include_router(stock.router, tags=["Stock"])
app.include_router(insights.router, prefix="/api/v1/insights", tags=["Insights"])
app.include_router(admin.router, prefix="/admin", tags=["Admin"])
app.include_router(feedback.router, prefix="/api/v1/feedback", tags=["Feedback"])