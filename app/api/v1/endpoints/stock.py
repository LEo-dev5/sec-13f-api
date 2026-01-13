from pathlib import Path
from fastapi import APIRouter, Request, HTTPException
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from sqlalchemy import desc, func

from app.db.database import SessionLocal
from app.db.models import Institution, Holding

router = APIRouter()
TEMPLATE_DIR = Path(__file__).resolve().parent.parent.parent.parent.parent / "app" / "templates"
templates = Jinja2Templates(directory=str(TEMPLATE_DIR))

@router.get("/stock/{ticker}")
async def stock_detail(request: Request, ticker: str):
    db: Session = SessionLocal()
    try:
        # 🚨 [수정] 대문자 강제 변환 (tsla -> TSLA)
        target_ticker = ticker.upper().strip()

        holdings = (
            db.query(
                Institution.name,
                Institution.cik,
                func.sum(Holding.shares).label("shares"),
                func.sum(Holding.value).label("value")
            )
            .join(Holding, Institution.id == Holding.institution_id)
            .filter(Holding.ticker == target_ticker) # 대문자로 검색
            .group_by(Institution.id, Institution.name, Institution.cik)
            .order_by(desc("shares"))
            .limit(100)
            .all()
        )
        
        # 데이터가 없어도 에러 페이지 대신 빈 화면이라도 띄워줌
        if not holdings:
            return templates.TemplateResponse("stock_detail.html", {
                "request": request, "ticker": target_ticker, "stock_name": target_ticker, 
                "holdings": [], "stats": {"total_shares": 0, "total_value": 0, "count": 0}
            })

        total_shares = sum(h.shares for h in holdings)
        total_value = sum(h.value for h in holdings)
        
        return templates.TemplateResponse("stock_detail.html", {
            "request": request,
            "ticker": target_ticker,
            "stock_name": target_ticker,
            "holdings": holdings,
            "stats": {
                "total_shares": total_shares,
                "total_value": total_value,
                "count": len(holdings)
            }
        })
    finally:
        db.close()