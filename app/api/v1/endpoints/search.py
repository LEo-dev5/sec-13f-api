from pathlib import Path
from fastapi import APIRouter, Request, Query, Depends
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from sqlalchemy import or_, desc

from app.db.database import get_db
from app.db.models import Institution, StockSummary

router = APIRouter()
TEMPLATE_DIR = Path(__file__).resolve().parent.parent.parent.parent.parent / "app" / "templates"
templates = Jinja2Templates(directory=str(TEMPLATE_DIR))

# 한글 검색어 매핑 (필수 종목들)
KOREAN_KEYWORD_MAP = {
    "테슬라": "TSLA", "애플": "AAPL", "마이크로소프트": "MSFT", "엔비디아": "NVDA",
    "아마존": "AMZN", "구글": "GOOGL", "메타": "META", "넷플릭스": "NFLX", 
    "삼성": "SAMSUNG", "쿠팡": "CPNG", "티에스엠씨": "TSM",
    "버크셔": "BRK.B", "코카콜라": "KO", "펩시": "PEP",
    "제이피모건": "JPM", "모건스탠리": "MS", "리얼티인컴": "O"
}

@router.get("/search")
async def search_page(request: Request, q: str = Query("", min_length=1), db: Session = Depends(get_db)):
    raw_query = q.strip()
    search_query = KOREAN_KEYWORD_MAP.get(raw_query, raw_query) 
    ticker_query = search_query.upper()

    try:
        if not raw_query:
            return templates.TemplateResponse("search_result.html", {"request": request, "query": "", "institutions": [], "stocks": []})

        # 1. 기관 검색
        institutions = db.query(Institution).filter(
            or_(
                Institution.name.ilike(f"%{raw_query}%"),
                Institution.name.ilike(f"%{search_query}%")
            )
        ).limit(50).all()

        # 2. 종목 검색 (StockSummary 조회)
        # 이름이나 티커에 검색어가 '포함'만 되어도 다 가져옴
        stocks = (
            db.query(
                StockSummary.name,
                StockSummary.ticker,
                StockSummary.total_value,
                StockSummary.holder_count.label("count") 
            )
            .filter(
                or_(
                    StockSummary.name.ilike(f"%{raw_query}%"),     
                    StockSummary.name.ilike(f"%{search_query}%"),  
                    StockSummary.ticker.ilike(f"%{ticker_query}%") # 앞뒤 어디든 포함되면 OK
                )
            )
            .order_by(desc(StockSummary.total_value)) # 자산 규모 순으로 정렬 (유명한 게 위로)
            .limit(50)
            .all()
        )
        
        return templates.TemplateResponse("search_result.html", {
            "request": request, "query": raw_query, 
            "institutions": institutions, "stocks": stocks
        })
        
    except Exception as e:
        print(f"Search Error: {e}")
        return templates.TemplateResponse("search_result.html", {"request": request, "query": q, "institutions": [], "stocks": []})

# 자동완성 API
@router.get("/api/v1/search/suggest")
async def suggest_keywords(q: str = Query(..., min_length=1), db: Session = Depends(get_db)):
    query = q.strip().upper()
    
    tickers = db.query(StockSummary.ticker, StockSummary.name)\
        .filter(
            or_(
                StockSummary.ticker.ilike(f"{query}%"), 
                StockSummary.name.ilike(f"%{query}%")
            )
        )\
        .order_by(desc(StockSummary.total_value))\
        .limit(5).all()
        
    institutions = db.query(Institution.name)\
        .filter(Institution.name.ilike(f"%{query}%"))\
        .limit(5).all()

    results = []
    for t in tickers: results.append({"name": t.name, "ticker": t.ticker, "type": "stock"})
    for i in institutions: results.append({"name": i.name, "ticker": None, "type": "institution"})
        
    return results