# app/api/v1/endpoints/home.py

from fastapi import APIRouter, Request
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from pathlib import Path
from sqlalchemy import desc

from app.db.database import SessionLocal
from app.db.models import Institution, Holding, Insight  # 👈 Insight 추가!

router = APIRouter()

BASE_DIR = Path(__file__).resolve().parent.parent.parent.parent.parent
TEMPLATE_DIR = BASE_DIR / "app" / "templates"
templates = Jinja2Templates(directory=str(TEMPLATE_DIR))

# 유명한 투자자 CIK 리스트
GURU_CIKS = ["0001067983", "0001649339", "0001350694"]

@router.get("/")
async def home(request: Request):
    db: Session = SessionLocal()
    try:
        # 1. Guru 3인방 데이터 가져오기
        gurus = db.query(Institution).filter(Institution.cik.in_(GURU_CIKS)).all()
        
        guru_data = []
        for guru in gurus:
            holdings = db.query(Holding).filter(Holding.institution_id == guru.id).order_by(desc(Holding.value)).all()
            
            total_value = sum(h.value for h in holdings)
            if total_value == 0: total_value = 1 

            top_5 = holdings[:5]
            chart_labels = [h.name for h in top_5]
            chart_data = [round((h.value / total_value) * 100, 1) for h in top_5]
            
            others_value = total_value - sum(h.value for h in top_5)
            if others_value > 0:
                chart_labels.append("Others")
                chart_data.append(round((others_value / total_value) * 100, 1))

            guru_data.append({
                "name": guru.name,
                "cik": guru.cik,
                "labels": chart_labels,
                "data": chart_data,
                "total_assets": total_value
            })

        # 🚨 2. [추가] 최신 인사이트(카드뉴스) 가져오기 (최신순 6개)
        recent_insights = db.query(Insight).order_by(desc(Insight.created_at)).limit(6).all()

        return templates.TemplateResponse("index.html", {
            "request": request,
            "gurus": guru_data,
            "insights": recent_insights  # 👈 HTML로 배달!
        })
    finally:
        db.close()