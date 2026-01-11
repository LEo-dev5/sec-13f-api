# app/api/v1/endpoints/search.py
from pathlib import Path
from fastapi import APIRouter, Request, Query
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from sqlalchemy import or_, func, desc

from app.db.database import SessionLocal
from app.db.models import Institution, Holding

router = APIRouter()

BASE_DIR = Path(__file__).resolve().parent.parent.parent.parent.parent
TEMPLATE_DIR = BASE_DIR / "app" / "templates"
templates = Jinja2Templates(directory=str(TEMPLATE_DIR))

@router.get("/search")
async def search_page(request: Request, q: str = Query("", min_length=1)):
    db: Session = SessionLocal()
    try:
        query = q.strip()
        if not query:
            return templates.TemplateResponse("search_result.html", {
                "request": request, "query": "", "institutions": [], "stocks": []
            })

        # 1. 기관 검색
        institutions = db.query(Institution).filter(
            Institution.name.ilike(f"%{query}%")
        ).all()
        
        # 2. 종목 검색 (🚨 수정: 티커가 없는 '유령 데이터'는 제외!)
        stocks = (
            db.query(
                func.max(Holding.name).label("name"), 
                Holding.ticker, 
                func.count(Holding.institution_id).label("count"), 
                func.sum(Holding.value).label("total_value")       
            )
            .filter(
                # 검색어 조건
                or_(
                    Holding.name.ilike(f"%{query}%"),
                    Holding.ticker.ilike(f"%{query}%")
                )
            )
            # 🚨 [핵심 추가] 티커가 비어있으면 링크가 깨지므로 결과에서 뺍니다.
            .filter(
                Holding.ticker != None,
                Holding.ticker != ""
            )
            .group_by(Holding.ticker)
            .order_by(desc("total_value"))
            .limit(50)
            .all()
        )
        
        return templates.TemplateResponse("search_result.html", {
            "request": request,
            "query": query,
            "institutions": institutions,
            "stocks": stocks
        })
        
    finally:
        db.close()