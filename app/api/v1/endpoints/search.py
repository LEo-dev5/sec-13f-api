# app/api/v1/endpoints/search.py
from pathlib import Path
from fastapi import APIRouter, Request, Query
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from sqlalchemy import or_, func, desc # func, desc 추가

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

        # 1. 기관 검색 (기존 동일)
        institutions = db.query(Institution).filter(
            Institution.name.ilike(f"%{query}%")
        ).all()
        
        # 2. [변경] 종목 검색 -> '종목별'로 그룹화해서 가져오기
        # "KO"를 포함하는 종목을 찾고, 그 종목을 몇 개의 기관이 가지고 있는지(count) 셉니다.
        stocks = (
            db.query(
                Holding.name, 
                Holding.ticker, 
                func.count(Holding.institution_id).label("count"), # 보유 기관 수
                func.sum(Holding.value).label("total_value")       # 총 평가액 합계
            )
            .filter(
                or_(
                    Holding.name.ilike(f"%{query}%"),
                    Holding.ticker.ilike(f"%{query}%")
                )
            )
            .group_by(Holding.ticker) # 티커 기준으로 묶기 (중복 제거 효과)
            .order_by(desc("total_value")) # 보유액이 큰 순서대로 정렬
            .limit(50) # 너무 많으면 끊기
            .all()
        )
        
        return templates.TemplateResponse("search_result.html", {
            "request": request,
            "query": query,
            "institutions": institutions,
            "stocks": stocks # holdings -> stocks로 이름 변경
        })
        
    finally:
        db.close()