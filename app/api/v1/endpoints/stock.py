# app/api/v1/endpoints/stock.py
from pathlib import Path
from fastapi import APIRouter, Request
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from sqlalchemy import desc

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
        # 1. 이 종목을 보유한 모든 기관 찾기
        # (보유 주식 수 많은 순서로 정렬)
        holdings = (
            db.query(Holding)
            .filter(Holding.ticker == ticker)
            .order_by(desc(Holding.shares))
            .limit(100) # 상위 100개 기관만 (너무 많음 방지)
            .all()
        )
        
        if not holdings:
            return {"error": "데이터가 없습니다."}

        stock_name = holdings[0].name # 이름은 첫 번째 데이터에서 가져옴
        
        # 2. 통계 계산
        total_shares = sum(h.shares for h in holdings)
        total_value = sum(h.value for h in holdings)
        institution_count = len(holdings)

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