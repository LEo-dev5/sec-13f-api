# app/api/v1/endpoints/admin.py (덮어쓰기)

import asyncio
import os
import secrets
import random
from pathlib import Path
from fastapi import APIRouter, Request, Depends, HTTPException, status, BackgroundTasks
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from sqlalchemy import text, desc
from dotenv import load_dotenv

# 서비스 & DB 로직
from app.db.database import get_db, SessionLocal
from app.db.models import Institution, Insight, Feedback # 👈 Feedback 추가
from app.services.sec_service import fetch_all_13f_ciks
from app.services.db_service import update_institution_to_db

load_dotenv()
router = APIRouter()
security = HTTPBasic()
templates = Jinja2Templates(directory="app/templates")

TARGET_CIKS = ["0001067983", "0001350694", "0001649339"]

def get_current_username(credentials: HTTPBasicCredentials = Depends(security)):
    correct_username = os.getenv("ADMIN_USERNAME", "admin")
    correct_password = os.getenv("ADMIN_PASSWORD", "secret")
    is_correct_username = secrets.compare_digest(credentials.username, correct_username)
    is_correct_password = secrets.compare_digest(credentials.password, correct_password)
    if not (is_correct_username and is_correct_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="관리자 권한 필요", headers={"WWW-Authenticate": "Basic"})
    return credentials.username

# 1. 대시보드 (피드백 목록 추가)
@router.get("/")
async def admin_dashboard(request: Request, db: Session = Depends(get_db), username: str = Depends(get_current_username)):
    inst_count = db.query(Institution).count()
    insight_count = db.query(Insight).count()
    
    insight_list = db.query(Insight).order_by(desc(Insight.created_at)).all()
    # 🚨 [추가] 피드백 목록 가져오기
    feedback_list = db.query(Feedback).order_by(desc(Feedback.created_at)).all()
    
    return templates.TemplateResponse("admin_dashboard.html", {
        "request": request,
        "username": username,
        "inst_count": inst_count,
        "insight_count": insight_count,
        "insights": insight_list,
        "feedbacks": feedback_list # 👈 HTML로 전달
    })

# ... (크롤링, 업데이트 로직은 기존과 동일하므로 생략 - 그대로 두세요) ...

# 2. 피드백 삭제 API (추가)
@router.delete("/feedback/{feedback_id}")
async def delete_feedback(feedback_id: int, db: Session = Depends(get_db)):
    try:
        fb = db.query(Feedback).filter(Feedback.id == feedback_id).first()
        if fb:
            db.delete(fb)
            db.commit()
            return {"status": "success"}
        return {"status": "error", "message": "Not found"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

# ... (기타 reset-cache, fix-names 등 기존 코드 유지) ...