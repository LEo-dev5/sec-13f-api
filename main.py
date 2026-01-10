# app/main.py

from fastapi import FastAPI
from contextlib import asynccontextmanager
from fastapi.staticfiles import StaticFiles
from app.api.v1.endpoints import feedback

# 1. 라우터 파일들 임포트
from app.api.v1.endpoints import sec, admin, home, search, stock, insights
from app.services.ticker_service import load_sec_tickers

# 2. 수명 주기 설정
@asynccontextmanager
async def lifespan(app: FastAPI):
    print("🚀 [System] 서버 시작: 티커 데이터 로딩 중...")
    await load_sec_tickers()
    yield
    print("👋 [System] 서버 종료")

app = FastAPI(lifespan=lifespan)

# 3. 정적 파일 연결
app.mount("/static", StaticFiles(directory="app/static"), name="static")

# 4. 라우터 등록 (이 부분이 404 해결의 핵심입니다!)
# -----------------------------------------------------

# 메인 홈
app.include_router(home.router, tags=["Home"])

# 기관 상세 페이지 & 분석 (/api/v1/sec/dashboard/...)
app.include_router(sec.router, prefix="/api/v1/sec", tags=["SEC"])

# 검색
app.include_router(search.router, tags=["Search"])

# 주식 상세
app.include_router(stock.router, tags=["Stock"])

# 인사이트
app.include_router(insights.router, prefix="/api/v1/insights", tags=["Insights"])

# 관리자
app.include_router(admin.router, prefix="/admin", tags=["Admin"])
# 피드백
app.include_router(feedback.router, prefix="/api/v1/feedback", tags=["Feedback"]) # 👈 추가