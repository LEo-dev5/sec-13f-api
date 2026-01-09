# app/api/v1/endpoints/home.py
from fastapi import APIRouter, Request
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from pathlib import Path
from sqlalchemy import desc

from app.db.database import SessionLocal
from app.db.models import Institution, Holding

router = APIRouter()

BASE_DIR = Path(__file__).resolve().parent.parent.parent.parent.parent
TEMPLATE_DIR = BASE_DIR / "app" / "templates"
templates = Jinja2Templates(directory=str(TEMPLATE_DIR))

# 유명한 투자자 CIK 리스트 (버크셔, 사이언, 브리지워터)
GURU_CIKS = ["0001067983", "0001649339", "0001350694"]

@router.get("/")
async def home(request: Request):
    db: Session = SessionLocal()
    try:
        # 1. Guru 3인방 데이터 강제 소환
        gurus = db.query(Institution).filter(Institution.cik.in_(GURU_CIKS)).all()
        
        guru_data = []
        for guru in gurus:
            # 보유 종목 가져오기 (평가액 순)
            holdings = db.query(Holding).filter(Holding.institution_id == guru.id).order_by(desc(Holding.value)).all()
            
            total_value = sum(h.value for h in holdings)
            if total_value == 0: total_value = 1 # 0 나누기 방지

            # 상위 5개 종목 비중 계산
            top_5 = holdings[:5]
            chart_labels = [h.name for h in top_5]
            chart_data = [round((h.value / total_value) * 100, 1) for h in top_5]
            
            # 기타(Others) 처리
            others_value = total_value - sum(h.value for h in top_5)
            if others_value > 0:
                chart_labels.append("Others")
                chart_data.append(round((others_value / total_value) * 100, 1))

            # 🚨 [수정 포인트] 객체(guru) 대신 문자열(name, cik)로 풀어서 저장
            # 이렇게 해야 HTML에서 tojson으로 에러 없이 변환 가능합니다.
            guru_data.append({
                "name": guru.name,  # 👈 변경됨
                "cik": guru.cik,    # 👈 변경됨
                "labels": chart_labels,
                "data": chart_data,
                "total_assets": total_value
            })

        return templates.TemplateResponse("index.html", {
            "request": request,
            "gurus": guru_data
        })
    finally:
        db.close()