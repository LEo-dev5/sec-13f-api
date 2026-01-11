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
        
        # 2. 종목 검색 (PostgreSQL GroupingError 수정됨 🛠️)
        stocks = (
            db.query(
                # 🚨 핵심 수정: 이름을 그룹핑 함수(max)로 감싸야 에러가 안 납니다!
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
            .group_by(Holding.ticker) # 티커 기준으로 그룹화
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