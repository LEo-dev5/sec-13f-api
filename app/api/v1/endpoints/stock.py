from pathlib import Path
from fastapi import APIRouter, Request
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from sqlalchemy import desc, func

from app.db.database import SessionLocal
from app.db.models import Institution, Holding

router = APIRouter()

BASE_DIR = Path(__file__).resolve().parent.parent.parent.parent.parent
TEMPLATE_DIR = BASE_DIR / "app" / "templates"
templates = Jinja2Templates(directory=str(TEMPLATE_DIR))

@router.get("/stock/{ticker}")
async def stock_detail(request: Request, ticker: str):
    db: Session = SessionLocal()
    try:
        # 1. [핵심 수정] 기관별로 그룹화(Group By)해서 합산하기
        # 같은 기관이 여러 번 신고했거나 자회사가 있어도 하나로 합칩니다.
        holdings = (
            db.query(
                Institution.name,
                Institution.cik,
                func.sum(Holding.shares).label("shares"),  # 주식 수 합산
                func.sum(Holding.value).label("value")     # 평가액 합산
            )
            .join(Holding, Institution.id == Holding.institution_id) # 테이블 연결
            .filter(Holding.ticker == ticker)
            .group_by(Institution.id, Institution.name, Institution.cik) # 기관별 묶기
            .order_by(desc("shares")) # 주식 수 많은 순 정렬
            .limit(100)
            .all()
        )
        
        if not holdings:
            return templates.TemplateResponse("stock_detail.html", {
                "request": request, "ticker": ticker, "stock_name": ticker, 
                "holdings": [], "stats": {"total_shares": 0, "total_value": 0, "count": 0}
            })

        # 2. 통계 계산 (합산된 데이터 기준)
        total_shares = sum(h.shares for h in holdings)
        total_value = sum(h.value for h in holdings)
        institution_count = len(holdings)

        # 종목 이름은 첫 번째 데이터의 ticker로 대체 (필요 시 별도 매핑 가능)
        stock_name = ticker 

        return templates.TemplateResponse("stock_detail.html", {
            "request": request,
            "ticker": ticker,
            "stock_name": stock_name,
            "holdings": holdings,
            "stats": {
                "total_shares": total_shares,
                "total_value": total_value,
                "count": institution_count
            }
        })
    finally:
        db.close()