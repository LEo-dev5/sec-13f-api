from pathlib import Path
from fastapi import APIRouter, Request, Query, Depends
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from sqlalchemy import or_, desc, func

from app.db.database import get_db
from app.db.models import Institution, Holding, StockSummary # 👈 StockSummary 추가됨!

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

        # 1. 기관 검색 (기존과 동일 - 인덱스 사용)
        inst_by_name = db.query(Institution).filter(
            or_(Institution.name.ilike(f"%{raw_query}%"), Institution.name.ilike(f"%{search_query}%"))
        ).limit(50).all()

        # 티커로 기관 찾기 (StockSummary 덕분에 이것도 가볍게 가능하지만 기존 유지)
        inst_ids_by_ticker = db.query(Holding.institution_id).filter(Holding.ticker == ticker_query).distinct().all()
        target_ids = [i[0] for i in inst_ids_by_ticker]
        
        inst_by_ticker = []
        if target_ids:
            inst_by_ticker = db.query(Institution).filter(Institution.id.in_(target_ids)).limit(50).all()

        all_institutions = list({inst.id: inst for inst in (inst_by_name + inst_by_ticker)}.values())

        # 🚨 2. 종목 검색 [속도 개선의 핵심!]
        # 350만 개 Holding 테이블 대신 -> 1만 개 StockSummary 테이블 조회 (0.001초 소요)
        stocks = (
            db.query(StockSummary)
            .filter(
                or_(
                    StockSummary.name.ilike(f"%{raw_query}%"),     # 이름 검색
                    StockSummary.name.ilike(f"%{search_query}%"),  # 매핑된 이름 검색
                    StockSummary.ticker == ticker_query             # 티커 검색
                )
            )
            .order_by(desc(StockSummary.total_value)) # 자산 규모 순 정렬
            .limit(20)
            .all()
        )
        
        # 템플릿 호환성을 위해 변수명 맞춤 (count -> holder_count)
        # StockSummary 모델 필드명(total_value, holder_count)을 그대로 사용
        
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
    
    # 🚨 자동완성도 StockSummary 사용 (초고속)
    tickers = db.query(StockSummary.ticker, StockSummary.name)\
        .filter(StockSummary.ticker.ilike(f"{query}%"))\
        .limit(5).all()
        
    institutions = db.query(Institution.name).filter(Institution.name.ilike(f"%{query}%")).limit(5).all()

    results = []
    for t in tickers: results.append({"name": t.name, "ticker": t.ticker, "type": "stock"})
    for i in institutions: results.append({"name": i.name, "ticker": None, "type": "institution"})
        
    return results