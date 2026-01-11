# app/main.py
import os
from fastapi import FastAPI
from contextlib import asynccontextmanager
from fastapi.staticfiles import StaticFiles

# 🚨 1. DB 관련 모듈 임포트 (필수!)
from app.db.database import engine, Base
# 모델들을 임포트해야 Base가 "아 이런 테이블을 만들어야 하는구나" 하고 알 수 있습니다.
from app.db.models import Institution, Holding, Insight, Feedback 

# 라우터 및 서비스 임포트
from app.api.v1.endpoints import sec, admin, home, search, stock, insights, feedback
# from app.services.ticker_service import load_sec_tickers # (일단 주석 유지)

# 2. 수명 주기 설정
@asynccontextmanager
async def lifespan(app: FastAPI):
    print("🚀 [System] 서버 부팅 중...")
    
    # 🚨 [핵심 수정] DB 테이블이 없으면 자동으로 생성합니다!
    # 이 코드가 "no such table" 에러를 해결해줍니다.
    try:
        Base.metadata.create_all(bind=engine)
        print("✅ [System] 데이터베이스 테이블 생성 완료!")
    except Exception as e:
        print(f"🔥 [System] 테이블 생성 중 오류: {e}")

    # (티커 다운로드는 일단 꺼둠 - 빠른 부팅 위함)
    # await load_sec_tickers() 
    
    yield
    print("👋 [System] 서버 종료")

app = FastAPI(lifespan=lifespan)

# 3. 폴더 생성 (없으면 에러나니까)
os.makedirs("app/static/uploads", exist_ok=True)

# 4. 정적 파일 연결
app.mount("/static", StaticFiles(directory="app/static"), name="static")

# 5. 라우터 등록
app.include_router(home.router, tags=["Home"])
app.include_router(sec.router, prefix="/api/v1/sec", tags=["SEC"])
app.include_router(search.router, tags=["Search"])
app.include_router(stock.router, tags=["Stock"])
app.include_router(insights.router, prefix="/api/v1/insights", tags=["Insights"])
app.include_router(admin.router, prefix="/admin", tags=["Admin"])
app.include_router(feedback.router, prefix="/api/v1/feedback", tags=["Feedback"])