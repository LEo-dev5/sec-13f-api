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

# 1. HTML 검색 페이지 (주소: /search)
@router.get("/search")
async def search_page(request: Request, q: str = Query("", min_length=1), db: Session = Depends(get_db)):
    raw_query = q.strip()
    search_query = KOREAN_KEYWORD_MAP.get(raw_query, raw_query) 
    ticker_query = search_query.upper()

    try:
        if not raw_query:
            return templates.TemplateResponse("search_result.html", {"request": request, "query": "", "institutions": [], "stocks": []})

        # 기관 검색
        inst_by_name = db.query(Institution).filter(
            or_(Institution.name.ilike(f"%{raw_query}%"), Institution.name.ilike(f"%{search_query}%"))
        ).limit(50).all()

        inst_ids_by_ticker = db.query(Holding.institution_id).filter(Holding.ticker == ticker_query).distinct().all()
        target_ids = [i[0] for i in inst_ids_by_ticker]
        
        inst_by_ticker = []
        if target_ids:
            inst_by_ticker = db.query(Institution).filter(Institution.id.in_(target_ids)).limit(50).all()

        all_institutions = list({inst.id: inst for inst in (inst_by_name + inst_by_ticker)}.values())

        # 종목 검색 (강력 필터 적용)
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
            .filter(func.length(Holding.ticker) <= 5) # 🚨 5글자 넘는 티커 제거 (중복 해결)
            .filter(~Holding.ticker.contains(" "))    # 🚨 공백 포함 티커 제거
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

# 2. 자동완성 API (주소: /api/v1/search/suggest)
# 🚨 [수정] 프론트엔드 요청 주소와 정확히 일치시켰습니다.
@router.get("/api/v1/search/suggest")
async def suggest_keywords(q: str = Query(..., min_length=1), db: Session = Depends(get_db)):
    query = q.strip().upper()
    
    # 자동완성에도 동일한 필터 적용
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