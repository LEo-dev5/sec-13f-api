from pathlib import Path
from fastapi import APIRouter, Request, Query, Depends
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from sqlalchemy import or_, desc

from app.db.database import get_db
from app.db.models import Institution, Holding, StockSummary

router = APIRouter()
TEMPLATE_DIR = Path(__file__).resolve().parent.parent.parent.parent.parent / "app" / "templates"
templates = Jinja2Templates(directory=str(TEMPLATE_DIR))

# 한글 매핑 (보조 수단)
KOREAN_KEYWORD_MAP = {
    "테슬라": "TSLA", "애플": "AAPL", "마이크로소프트": "MSFT", "엔비디아": "NVDA",
    "아마존": "AMZN", "구글": "GOOGL", "알파벳": "GOOGL", "메타": "META",
    "넷플릭스": "NFLX", "삼성": "SAMSUNG", "쿠팡": "CPNG", "티에스엠씨": "TSM",
    "버크셔": "BRK.B", "버크셔해서웨이": "BRK.B", "코카콜라": "KO", "펩시": "PEP",
    "제이피모건": "JPM", "모건스탠리": "MS", "골드만삭스": "GS", "뱅크오브아메리카": "BAC",
    "리얼티인컴": "O", "배당": "SCHD"
}

@router.get("/search")
async def search_page(request: Request, q: str = Query("", min_length=1), db: Session = Depends(get_db)):
    raw_query = q.strip()
    # 한글이면 영어 티커로 변환, 아니면 그대로 대문자 변환
    search_query = KOREAN_KEYWORD_MAP.get(raw_query, raw_query) 
    ticker_query = search_query.upper()

    try:
        if not raw_query:
            return templates.TemplateResponse("search_result.html", {"request": request, "query": "", "institutions": [], "stocks": []})

        # 1. 기관 검색 (이름으로 넓게 검색)
        inst_by_name = db.query(Institution).filter(
            or_(
                Institution.name.ilike(f"%{raw_query}%"),
                Institution.name.ilike(f"%{search_query}%")
            )
        ).limit(50).all()

        # 2. 종목 검색 (StockSummary 사용)
        # 🚨 [수정] 정확한 일치(==) 대신 ilike 사용 -> "JPM" 검색시 "JPM" 포함한 모든 것 검색 가능
        stocks = (
            db.query(
                StockSummary.name,
                StockSummary.ticker,
                StockSummary.total_value,
                StockSummary.holder_count.label("count") 
            )
            .filter(
                or_(
                    StockSummary.name.ilike(f"%{raw_query}%"),     # 이름에 포함
                    StockSummary.name.ilike(f"%{search_query}%"),  # 매핑된 이름에 포함
                    StockSummary.ticker.ilike(f"{ticker_query}%")   # 🚨 티커로 시작하는 것 (JPM -> JPM, JPM.X 등)
                )
            )
            .order_by(desc(StockSummary.total_value)) # 자산 많은 순
            .limit(50) # 결과 개수 늘림
            .all()
        )
        
        # 기관 검색 결과와 합치기 (종목 검색 결과가 없으면 기관만이라도 보여줌)
        return templates.TemplateResponse("search_result.html", {
            "request": request, "query": raw_query, 
            "institutions": inst_by_name, "stocks": stocks
        })
        
    except Exception as e:
        print(f"Search Error: {e}")
        return templates.TemplateResponse("search_result.html", {"request": request, "query": q, "institutions": [], "stocks": []})

@router.get("/suggest")
async def suggest_keywords(q: str = Query(..., min_length=1), db: Session = Depends(get_db)):
    query = q.strip().upper()
    
    # 자동완성 범위도 확장
    tickers = db.query(StockSummary.ticker, StockSummary.name)\
        .filter(
            or_(
                StockSummary.ticker.ilike(f"{query}%"), 
                StockSummary.name.ilike(f"%{query}%")
            )
        )\
        .limit(5).all()
        
    institutions = db.query(Institution.name)\
        .filter(Institution.name.ilike(f"%{query}%"))\
        .limit(5).all()

    results = []
    for t in tickers: results.append({"name": t.name, "ticker": t.ticker, "type": "stock"})
    for i in institutions: results.append({"name": i.name, "ticker": None, "type": "institution"})
        
    return results

# 프론트엔드 주소 호환용 (API 경로 추가)
@router.get("/api/v1/search/suggest")
async def suggest_keywords_api(q: str = Query(..., min_length=1), db: Session = Depends(get_db)):
    return await suggest_keywords(q, db)