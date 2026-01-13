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
    "어도비": "ADBE",
    "세일즈포스": "CRM",
    "AMD": "AMD",
    "퀄컴": "QCOM",
    "시스코": "CSCO",
    "홈디포": "HD",
    "코스트코": "COST",
    "JP모건": "JPM",
    "골드만 삭스": "GS",
    "모건 스탠리": "MS",
    "뱅가드": "VTI",
    "블랙록": "BLK",
    "피델리티": "FNF",
    "찰스 슈왑": "SCHW",
    "T모바일": "TMUS",
    "AT&T": "T",
    "버라이즌": "VZ",
    "보잉": "BA",
    "포드": "F",
    "제너럴 모터스": "GM",
    "쉐브론": "CVX",
    "길리어드 사이언스": "GILD",
    "암젠": "AMGN",
    "화이자": "PFE",
    "모더나": "MRNA",
    "노바백스": "NVAX",
    "바이오엔텍": "BNTX",
    "록히드 마틴": "LMT",
    "노스롭 그루먼": "NOC",
    "레이시온 테크놀로지": "RTX",
    "3M": "MMM",
    "GE": "GE",
    "시티그룹": "C",
    "웰스 파고": "WFC",
    "뱅크 오브 아메리카": "BAC",
    "PNC 파이낸셜": "PNC",    
    "US 뱅코프": "USB",
    "찰스 슈왑": "SCHW",
    "도이치 뱅크": "DB",
    "바클레이즈": "BCS",
    "HSBC": "HSBC",
    "로열 뱅크 오브 캐나다": "RY",
    "토론토 도미니언 뱅크": "TD",
    "뱅크 오브 뉴욕 멜론": "BK",
    "모건 스탠리": "MS",
    "골드만 삭스": "GS",
    "블랙스톤": "BX",
    "KKR": "KKR",
    "아폴로 글로벌 매니지먼트": "APO",
    "칼라일 그룹": "CG",
    "Oaktree Capital": "OAK",
    "Ares Management": "ARES",
    "Brookfield Asset Management": "BAM",
    "ge버노바" : "GEV",
   
           
    # 필요시 계속 추가
}

@router.get("/search")
async def search_page(request: Request, q: str = Query("", min_length=1), db: Session = Depends(get_db)):
    # 1. 검색어 전처리
    raw_query = q.strip()
    
    # 🇰🇷 [UX 핵심] 한글 검색어가 들어오면 영어 티커로 변환
    search_query = KOREAN_KEYWORD_MAP.get(raw_query, raw_query) 
    
    # 대문자 변환 (인덱스 활용을 위해)
    ticker_query = search_query.upper()

    try:  # 👈 여기가 빠져 있었습니다!
        if not raw_query:
            return templates.TemplateResponse("search_result.html", {
                "request": request, "query": "", "institutions": [], "stocks": []
            })

        # 2. 기관 검색 최적화 (쿼리 분리 전략)
        
        # A. 이름으로 기관 찾기 (3,000개 중 찾으므로 빠름)
        # 사용자가 'BlackRock' 이라고 쳤을 때를 대비해 raw_query나 search_query 모두 체크
        inst_by_name = db.query(Institution).filter(
            or_(
                Institution.name.ilike(f"%{raw_query}%"),
                Institution.name.ilike(f"%{search_query}%")
            )
        ).limit(50).all()

        # B. 티커로 기관 찾기 (인덱스 타면 0.01초 소요)
        # 'TSLA'를 가진 종목의 institution_id만 먼저 싹 가져옵니다.
        inst_ids_by_ticker = db.query(Holding.institution_id).filter(
            Holding.ticker == ticker_query # 🚨 == 사용 (Index Scan)
        ).distinct().all()
        
        # ID 리스트 추출 ([(1,), (5,)] -> [1, 5])
        target_ids = [id_tuple[0] for id_tuple in inst_ids_by_ticker]

        # C. 티커로 찾은 기관 데이터 가져오기
        inst_by_ticker = []
        if target_ids:
            inst_by_ticker = db.query(Institution).filter(
                Institution.id.in_(target_ids)
            ).limit(50).all()

        # D. 결과 합치기 (중복 제거)
        # 파이썬 리스트 컴프리헨션으로 중복 제거 및 합병
        all_institutions = list({inst.id: inst for inst in (inst_by_name + inst_by_ticker)}.values())

        # 3. 종목 검색 (섹션 하단 표시용)
        stocks = (
            db.query(
                func.max(Holding.name).label("name"), 
                Holding.ticker, 
                func.count(Holding.institution_id).label("count"), 
                func.sum(Holding.value).label("total_value")       
            )
            .filter(
                or_(
                    Holding.name.ilike(f"%{raw_query}%"), # 원래 이름 검색
                    Holding.name.ilike(f"%{search_query}%"), # 매핑된 이름 검색
                    Holding.ticker == ticker_query # 티커 정확 일치
                )
            )
            .filter(Holding.ticker != None)
            .group_by(Holding.ticker)
            .order_by(desc("total_value"))
            .limit(20)
            .all()
        )
        
        return templates.TemplateResponse("search_result.html", {
            "request": request,
            "query": raw_query,
            "institutions": all_institutions[:50], # 최대 50개 표시
            "stocks": stocks
        })
        
    except Exception as e:
        print(f"Search Error: {e}")
        return templates.TemplateResponse("search_result.html", {
            "request": request, "query": q, "institutions": [], "stocks": []
        })
    

@router.get("/suggest")
async def suggest_keywords(q: str = Query(..., min_length=1), db: Session = Depends(get_db)):
    query = q.strip().upper() # 대문자로 변환
    
    # 1. 티커로 검색 (우선순위 높음)
    # Holdings 테이블에서 티커가 일치하는 것 찾기 (중복 제거)
    tickers = db.query(Holding.ticker, Holding.name)\
        .filter(Holding.ticker.ilike(f"{query}%"))\
        .distinct(Holding.ticker)\
        .limit(5)\
        .all()
        
    # 2. 기관명으로 검색
    institutions = db.query(Institution.name)\
        .filter(Institution.name.ilike(f"%{query}%"))\
        .limit(5)\
        .all()

    results = []
    
    # 결과 포맷팅 (JSON으로 보낼 데이터)
    for t in tickers:
        results.append({"name": t.name, "ticker": t.ticker, "type": "stock"})
        
    for i in institutions:
        results.append({"name": i.name, "ticker": None, "type": "institution"})
        
    return results