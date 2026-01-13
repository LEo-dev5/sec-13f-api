from pathlib import Path
from fastapi import APIRouter, Request, Query, Depends
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from sqlalchemy import or_, func, desc

from app.db.database import get_db
from app.db.models import Institution, Holding

router = APIRouter()

BASE_DIR = Path(__file__).resolve().parent.parent.parent.parent.parent
TEMPLATE_DIR = BASE_DIR / "app" / "templates"
templates = Jinja2Templates(directory=str(TEMPLATE_DIR))

KOREAN_KEYWORD_MAP = {
    "테슬라": "TSLA",
    "애플": "AAPL",
    "마이크로소프트": "MSFT",
    "엔비디아": "NVDA",
    "아마존": "AMZN",
    "구글": "GOOGL",
    "알파벳": "GOOGL",
    "메타": "META",
    "페이스북": "META",
    "넷플릭스": "NFLX",
    "삼성": "SAMSUNG", 
    "쿠팡": "CPNG",
    "티에스엠씨": "TSM",
    "버크셔 해서웨이": "BRK.B",
    "비자": "V",
    "마스터카드": "MA",
    "존슨 앤 존슨": "JNJ",
    "엑슨 모빌": "XOM",
    "코카콜라": "KO",
    "펩시코": "PEP",
    "월마트": "WMT",
    "디즈니": "DIS",
    "스타벅스": "SBUX",
    "인텔": "INTC",
    "퀄컴": "QCOM",
    "시스코": "CSCO",
    "어도비": "ADBE",
    "세일즈포스": "CRM",
    "AMD": "AMD",
    "JP모건": "JPM",
    "골드만 삭스": "GS",
    "뱅가드": "VTI",
    "블랙록": "BLK",
    "스테이트 스트리트": "STT",
    "찰스 슈왑": "SCHW",
    "페이팔": "PYPL",
    "코스트코": "COST",
    "홈디포": "HD",
    "프로터 앤 갬블": "PG",
    "맥도날드": "MCD",
    "나이키": "NKE",
    "버라이즌": "VZ",
    "AT&T": "T",
    "모더나": "MRNA",
    "화이자": "PFE",
    "바이오엔텍": "BNTX",
    "존슨 앤드 존슨": "JNJ",
    "로슈": "RHHBY",
    "노바티스": "NVS",
    "길리어드 사이언스": "GILD",
    "암젠": "AMGN",
    # ... (기존 매핑 유지) ...
}

@router.get("/search")
async def search_page(request: Request, q: str = Query("", min_length=1), db: Session = Depends(get_db)):
    raw_query = q.strip()
    search_query = KOREAN_KEYWORD_MAP.get(raw_query, raw_query) 
    ticker_query = search_query.upper()

    try:
        if not raw_query:
            return templates.TemplateResponse("search_result.html", {
                "request": request, "query": "", "institutions": [], "stocks": []
            })

        # 1. 기관 검색
        inst_by_name = db.query(Institution).filter(
            or_(
                Institution.name.ilike(f"%{raw_query}%"),
                Institution.name.ilike(f"%{search_query}%")
            )
        ).limit(50).all()

        inst_ids_by_ticker = db.query(Holding.institution_id).filter(
            Holding.ticker == ticker_query 
        ).distinct().all()
        
        target_ids = [id_tuple[0] for id_tuple in inst_ids_by_ticker]

        inst_by_ticker = []
        if target_ids:
            inst_by_ticker = db.query(Institution).filter(
                Institution.id.in_(target_ids)
            ).limit(50).all()

        all_institutions = list({inst.id: inst for inst in (inst_by_name + inst_by_ticker)}.values())

        # 2. 종목 검색 (🚨 중복 제거 및 정크 데이터 필터링 적용)
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
            # 🧹 [핵심 필터] 티커가 5글자 이하이고, 공백이 없는 '진짜 티커'만 가져옵니다.
            .filter(Holding.ticker != None)
            .filter(func.length(Holding.ticker) <= 5) # "TESLA MTRS..." 같은 긴 이름 제외
            .filter(~Holding.ticker.contains(" "))    # 공백 있는 티커 제외
            .group_by(Holding.ticker)
            .order_by(desc("total_value"))
            .limit(20)
            .all()
        )
        
        return templates.TemplateResponse("search_result.html", {
            "request": request,
            "query": raw_query,
            "institutions": all_institutions[:50], 
            "stocks": stocks
        })
        
    except Exception as e:
        print(f"Search Error: {e}")
        return templates.TemplateResponse("search_result.html", {
            "request": request, "query": q, "institutions": [], "stocks": []
        })

@router.get("/suggest")
async def suggest_keywords(q: str = Query(..., min_length=1), db: Session = Depends(get_db)):
    query = q.strip().upper()
    
    # 자동완성에도 필터 적용
    tickers = db.query(Holding.ticker, Holding.name)\
        .filter(Holding.ticker.ilike(f"{query}%"))\
        .filter(func.length(Holding.ticker) <= 5)\
        .distinct(Holding.ticker)\
        .limit(5)\
        .all()
        
    institutions = db.query(Institution.name)\
        .filter(Institution.name.ilike(f"%{query}%"))\
        .limit(5)\
        .all()

    results = []
    for t in tickers:
        results.append({"name": t.name, "ticker": t.ticker, "type": "stock"})
    for i in institutions:
        results.append({"name": i.name, "ticker": None, "type": "institution"})
        
    return results