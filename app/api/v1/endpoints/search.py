from pathlib import Path
from fastapi import APIRouter, Request, Query, Depends
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from sqlalchemy import or_, func, desc

from app.db.database import get_db
from app.db.models import Institution, Holding

router = APIRouter()
TEMPLATE_DIR = Path(__file__).resolve().parent.parent.parent.parent.parent / "app" / "templates"
templates = Jinja2Templates(directory=str(TEMPLATE_DIR))

# 한글 매핑 사전
KOREAN_KEYWORD_MAP = {
    "테슬라": "TSLA", "애플": "AAPL", "마이크로소프트": "MSFT", "엔비디아": "NVDA",
    "아마존": "AMZN", "구글": "GOOGL", "알파벳": "GOOGL", "메타": "META",
    "넷플릭스": "NFLX", "삼성": "SAMSUNG", "쿠팡": "CPNG", "티에스엠씨": "TSM",
    "버크셔": "BRK.B", "버크셔해서웨이": "BRK.B", "코카콜라": "KO", "펩시": "PEP"
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
        inst_by_name = db.query(Institution).filter(
            or_(Institution.name.ilike(f"%{raw_query}%"), Institution.name.ilike(f"%{search_query}%"))
        ).limit(50).all()

        inst_ids_by_ticker = db.query(Holding.institution_id).filter(Holding.ticker == ticker_query).distinct().all()
        target_ids = [i[0] for i in inst_ids_by_ticker]
        
        inst_by_ticker = []
        if target_ids:
            inst_by_ticker = db.query(Institution).filter(Institution.id.in_(target_ids)).limit(50).all()

        all_institutions = list({inst.id: inst for inst in (inst_by_name + inst_by_ticker)}.values())

        # 2. 종목 검색 (🚨 필터 강화)
        stocks = (
            db.query(
                func.max(Holding.name).label("name"), 
                Holding.ticker, 
                func.count(Holding.institution_id).label("count"), 
                func.sum(Holding.value).label("total_value")       
            )
            .filter(
                or_(
                    Holding.name.ilike(f"%{raw_query}%"),
                    Holding.name.ilike(f"%{search_query}%"),
                    Holding.ticker == ticker_query 
                )
            )
            .filter(Holding.ticker != None)
            .filter(Holding.ticker != "")
            # 🚨 [중요] 글자수 제한: 5글자 초과는 무조건 제외 (BRK.B 같은 예외 고려해 6자 정도로 여유 둘 수도 있으나 5가 안전)
            .filter(func.length(Holding.ticker) <= 5)
            # 🚨 [중요] 공백 포함 시 제외 (TESLA MTRS... 제거)
            .filter(~Holding.ticker.contains(" "))
            .group_by(Holding.ticker)
            .order_by(desc("total_value"))
            .limit(20)
            .all()
        )
        
        return templates.TemplateResponse("search_result.html", {
            "request": request, "query": raw_query, 
            "institutions": all_institutions[:50], "stocks": stocks
        })
        
    except Exception as e:
        print(f"Search Error: {e}")
        return templates.TemplateResponse("search_result.html", {"request": request, "query": q, "institutions": [], "stocks": []})

@router.get("/api/v1/search/suggest")
async def suggest_keywords(q: str = Query(..., min_length=1), db: Session = Depends(get_db)):
    query = q.strip().upper()
    
    tickers = db.query(Holding.ticker, Holding.name)\
        .filter(Holding.ticker.ilike(f"{query}%"))\
        .filter(func.length(Holding.ticker) <= 5)\
        .filter(~Holding.ticker.contains(" "))\
        .distinct(Holding.ticker)\
        .limit(5).all()
        
    institutions = db.query(Institution.name).filter(Institution.name.ilike(f"%{query}%")).limit(5).all()

    results = []
    for t in tickers: results.append({"name": t.name, "ticker": t.ticker, "type": "stock"})
    for i in institutions: results.append({"name": i.name, "ticker": None, "type": "institution"})
        
    return results