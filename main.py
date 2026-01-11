# app/main.py
import os
from fastapi import FastAPI
from contextlib import asynccontextmanager
from fastapi.staticfiles import StaticFiles
from fastapi import Request
from fastapi import Response
from app.db.database import SessionLocal
from app.db.models import VisitLog

# 🚨 1. DB 관련 모듈 임포트 (필수!)
from app.db.database import engine, Base
# 모델들을 임포트해야 Base가 "아 이런 테이블을 만들어야 하는구나" 하고 알 수 있습니다.
from app.db.models import Institution, Holding, Insight, Feedback 

# 라우터 및 서비스 임포트
from app.api.v1.endpoints import sec, admin, home, search, stock, insights, feedback
# from app.services.ticker_service import load_sec_tickers # (일단 주석 유지)


is_production = os.getenv("RENDER") is not None

app = FastAPI(
    title="Easy13F",
    description="월가 대가들의 포트폴리오 분석 서비스",
    version="1.0.0",
    # 🔒 배포 환경이면 문서(Swagger UI) 숨기고, 디버그 끄기
    docs_url=None if is_production else "/docs",
    redoc_url=None if is_production else "/redoc",
    debug=False if is_production else True
)



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

@app.middleware("http")
async def log_visits(request: Request, call_next):
    response = await call_next(request)
    
    # 1. 정적 파일(.css, .js)이나 관리자 페이지, 파비콘은 카운트 제외
    if not request.url.path.startswith(("/static", "/admin", "/favicon.ico")):
        try:
            # 2. IP 주소 가져오기 (Render 같은 프록시 환경 고려)
            forwarded = request.headers.get("X-Forwarded-For")
            if forwarded:
                client_ip = forwarded.split(",")[0]
            else:
                client_ip = request.client.host

            # 3. DB에 기록 (비동기 흐름 방해 안 하도록 별도 세션 사용)
            db = SessionLocal()
            visit = VisitLog(ip_address=client_ip, path=request.url.path)
            db.add(visit)
            db.commit()
            db.close()
        except Exception as e:
            print(f"Logging Error: {e}") # 로깅 실패해도 사이트는 켜져야 함

    return response

@app.get("/sitemap.xml", include_in_schema=False)
async def sitemap():
    # 사이트의 주요 페이지 목록
    xml = """<?xml version="1.0" encoding="UTF-8"?>
    <urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
        <url>
            <loc>https://easy13f.com/</loc>
            <changefreq>daily</changefreq>
            <priority>1.0</priority>
        </url>
        <url>
            <loc>https://easy13f.com/search</loc>
            <changefreq>weekly</changefreq>
            <priority>0.8</priority>
        </url>
    </urlset>
    """
    return Response(content=xml, media_type="application/xml")


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