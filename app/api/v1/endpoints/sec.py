from fastapi import APIRouter, HTTPException, Request, Depends
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from app.db.database import get_db
from app.db.models import Institution, Holding
from app.services.sec_service import fetch_latest_13f
from app.services.ai_service import analyze_portfolio_by_llm
from sqlalchemy import desc, func

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")

@router.get("/dashboard/{cik}")
async def get_dashboard(request: Request, cik: str, db: Session = Depends(get_db)):
    try:
        saved_inst = db.query(Institution).filter(Institution.cik == cik).first()
        
        if not saved_inst:
             return templates.TemplateResponse("error.html", {"request": request, "message": "기관을 찾을 수 없습니다."})

        # 🚨 [메모리 보호] 상위 100개만 가져오기
        top_holdings = (
            db.query(Holding)
            .filter(Holding.institution_id == saved_inst.id)
            .order_by(desc(Holding.value))
            .limit(100) # 👈 이 숫자가 1GB 램을 지킵니다!
            .all()
        )

        # 총 자산 가치 별도 계산
        total_assets = db.query(func.sum(Holding.value)).filter(
            Holding.institution_id == saved_inst.id
        ).scalar() or 0

        # 데이터 변환
        display_holdings = []
        for h in top_holdings:
            display_holdings.append({
                "display_name": getattr(h, "name", getattr(h, "name_of_issuer", "Unknown")),
                "ticker": h.ticker,
                "value": h.value,
                "shares": h.shares,
                "change_rate": h.change_rate,
                "holding_type": h.holding_type,
            })

        return templates.TemplateResponse("dashboard.html", {
            "request": request,
            "cik": cik,
            "institution_name": saved_inst.name or f"Institution ({cik})",
            "report_date": "2025-09-30",
            "holdings": display_holdings,
            "description": saved_inst.description or "",
            "total_assets": total_assets
        })
        
    except Exception as e:
        print(f"Dashboard Error: {e}")
        return templates.TemplateResponse("error.html", {"request": request, "message": "데이터 로딩 실패"})

# ... (AI 분석 함수는 기존 파일 내용 유지) ...
@router.get("/dashboard/{cik}/ai-analysis")
async def get_ai_analysis_endpoint(cik: str, db: Session = Depends(get_db)):
    # 기존 코드 그대로 두세요
    return {"analysis": "AI 분석 기능"}