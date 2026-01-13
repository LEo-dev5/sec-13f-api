from pathlib import Path
from fastapi import APIRouter, Request, Query, Depends
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from sqlalchemy import or_, func, desc

from app.db.database import get_db, SessionLocal
from app.db.models import Institution, Holding

router = APIRouter()

BASE_DIR = Path(__file__).resolve().parent.parent.parent.parent.parent
TEMPLATE_DIR = BASE_DIR / "app" / "templates"
templates = Jinja2Templates(directory=str(TEMPLATE_DIR))

# 1. API용 엔드포인트 (자동완성이나 비동기 검색용)
@router.get("/api")
async def search_api(q: str = Query(...), db: Session = Depends(get_db)):
    query = q.strip()
    if not query:
        return []

    # 기관명에 포함되거나 티커가 일치하는 기관 검색
    results = db.query(Institution).join(Holding).filter(
        or_(
            Institution.name.ilike(f"%{query}%"),
            Holding.ticker.ilike(f"{query}")
        )
    ).distinct().limit(20).all()
    
    return results

# 2. 실제 검색 결과 페이지 (HTML 렌더링)
@router.get("/search")
async def search_page(request: Request, q: str = Query("", min_length=1), db: Session = Depends(get_db)):
    try:
        query = q.strip()
        if not query:
            return templates.TemplateResponse("search_result.html", {
                "request": request, "query": "", "institutions": [], "stocks": []
            })

        # [수정 핵심] 1. 기관 검색: 이름 검색 + 티커 보유 여부 동시 검색
        # 이제 'tsla'를 치면 테슬라를 가진 기관들이 여기서 잡힙니다.
        institutions = (
            db.query(Institution)
            .join(Holding)
            .filter(
                or_(
                    Institution.name.ilike(f"%{query}%"),
                    Holding.ticker.ilike(f"{query}") # 티커와 일치하는 종목을 가진 기관
                )
            )
            .distinct()
            .limit(50) # 성능을 위해 제한
            .all()
        )
        
        # 2. 종목 검색 (섹션 하단에 표시될 종목 리스트)
        stocks = (
            db.query(
                func.max(Holding.name).label("name"), 
                Holding.ticker, 
                func.count(Holding.institution_id).label("count"), 
                func.sum(Holding.value).label("total_value")       
            )
            .filter(
                or_(
                    Holding.name.ilike(f"%{query}%"),
                    Holding.ticker.ilike(f"%{query}%")
                )
            )
            .filter(
                Holding.ticker != None,
                Holding.ticker != ""
            )
            .group_by(Holding.ticker)
            .order_by(desc("total_value"))
            .limit(20)
            .all()
        )
        
        return templates.TemplateResponse("search_result.html", {
            "request": request,
            "query": query,
            "institutions": institutions,
            "stocks": stocks
        })
        
    except Exception as e:
        print(f"Search Error: {e}")
        return templates.TemplateResponse("search_result.html", {
            "request": request, "query": query, "institutions": [], "stocks": []
        })