import asyncio
import os
import secrets
import random
import gc  # 🧹 [추가] 쓰레기 청소부(Garbage Collector)
from pathlib import Path
from fastapi import APIRouter, Request, Depends, HTTPException, status, BackgroundTasks
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from sqlalchemy import text, desc, func, cast, Date
from dotenv import load_dotenv
from datetime import timedelta, datetime

from app.db.database import get_db, SessionLocal
from app.db.models import Institution, Insight, Feedback, VisitLog
from app.services.sec_service import fetch_all_13f_ciks
from app.services.db_service import update_institution_to_db

load_dotenv()
router = APIRouter()
security = HTTPBasic()
templates = Jinja2Templates(directory="app/templates")

# 🌟 [TOP 20] 유명 기관 리스트
TOP_FUNDS = [
    ("0001067983", "BERKSHIRE HATHAWAY INC"), 
    ("0001350694", "BRIDGEWATER ASSOCIATES, LP"), 
    ("0001649339", "SCION ASSET MANAGEMENT, LLC"), 
    ("000102909", "VANGUARD GROUP INC"),
    ("0001364742", "BLACKROCK INC"),
    ("0001166559", "GATES BILL & MELINDA FOUNDATION"),
    ("0001103804", "Viking Global Investors Lp"),
    ("0001540531", "TIGER GLOBAL MANAGEMENT LLC"),
    ("0000902219", "BAILLIE GIFFORD & CO"),
    ("0001040273", "Citadel Advisors Llc"),
    ("0001336528", "Pershing Square Capital Management, L.P."),
    ("0001172435", "ARK INVESTMENT MANAGEMENT LLC"), 
    ("0001423053", "SOROS FUND MANAGEMENT LLC"),
    ("0001541617", "Renaissance Technologies Llc"),
    ("0001569391", "DATAROMA"), 
]

# ... (인증 함수 get_current_username 등은 기존 유지) ...
def get_current_username(credentials: HTTPBasicCredentials = Depends(security)):
    correct_username = os.getenv("ADMIN_USERNAME")
    correct_password = os.getenv("ADMIN_PASSWORD")
    if not correct_username or not correct_password:
         raise HTTPException(status_code=503, detail="서버 보안 설정 오류")
    
    is_correct_username = secrets.compare_digest(credentials.username, correct_username)
    is_correct_password = secrets.compare_digest(credentials.password, correct_password)
    
    if not (is_correct_username and is_correct_password):
        raise HTTPException(status_code=401, detail="관리자 권한 필요", headers={"WWW-Authenticate": "Basic"})
    return credentials.username

def get_latest_filing_period():
    now = datetime.utcnow()
    if now.month < 2 or (now.month == 2 and now.day < 15): return now.year - 1, 3
    elif now.month < 5 or (now.month == 5 and now.day < 15): return now.year - 1, 4
    elif now.month < 8 or (now.month == 8 and now.day < 15): return now.year, 1
    elif now.month < 11 or (now.month == 11 and now.day < 15): return now.year, 2
    else: return now.year, 3

@router.get("/")
async def admin_dashboard(request: Request, db: Session = Depends(get_db), username: str = Depends(get_current_username)):
    # ... (대시보드 로직 기존 유지) ...
    inst_count = db.query(Institution).count()
    insight_count = db.query(Insight).count()
    insight_list = db.query(Insight).order_by(desc(Insight.created_at)).all()
    feedback_list = db.query(Feedback).order_by(desc(Feedback.created_at)).all()
    
    today = datetime.utcnow().date()
    seven_days_ago = today - timedelta(days=6)
    
    daily_stats = db.query(cast(VisitLog.timestamp, Date).label('date'), func.count(VisitLog.id).label('count')).filter(VisitLog.timestamp >= seven_days_ago).group_by(cast(VisitLog.timestamp, Date)).order_by(cast(VisitLog.timestamp, Date)).all()

    dates = []
    counts = []
    stats_dict = {stat.date: stat.count for stat in daily_stats}
    for i in range(7):
        d = seven_days_ago + timedelta(days=i)
        dates.append(d.strftime("%m-%d"))
        counts.append(stats_dict.get(d, 0))

    return templates.TemplateResponse("admin_dashboard.html", {
        "request": request, "username": username, "inst_count": inst_count,
        "insight_count": insight_count, "insights": insight_list, "feedbacks": feedback_list,
        "chart_dates": dates, "chart_counts": counts
    })

# ---------------------------------------------------------
# 🛠️ [안전 모드] 메모리 관리 강화
# ---------------------------------------------------------
async def run_gurus_update():
    print("🚀 [Admin] 유명 기관(TOP 20) 업데이트 시작...")
    db = SessionLocal()
    try:
        for cik, name in TOP_FUNDS:
            print(f"🔄 Processing Guru: {name}")
            existing = db.query(Institution).filter(Institution.cik == cik).first()
            if not existing:
                new_inst = Institution(cik=cik, name=name, is_featured=True)
                db.add(new_inst)
                db.commit()
                existing = new_inst
            
            await update_institution_to_db(db, cik, is_featured=True)
            
            # 🧹 [청소] 메모리 강제 정리
            existing.ai_summary = None 
            db.commit()
            gc.collect() # 램 확보!
            
            await asyncio.sleep(2) # 2초 휴식 (천천히)

    except Exception as e:
        print(f"🔥 Guru Update Failed: {e}")
    finally:
        db.close()
        gc.collect()
        print("🏁 [Admin] 유명 기관 업데이트 완료")

@router.post("/update/gurus")
async def update_gurus(background_tasks: BackgroundTasks, username: str = Depends(get_current_username)):
    background_tasks.add_task(run_gurus_update)
    return {"status": "success", "message": "TOP 20 기관 업데이트 시작!"}

async def run_crawler_process_all():
    target_year, target_qtr = get_latest_filing_period()
    print(f"🏎️ [Admin] 전체 기관 대규모 업데이트 시작... (타겟: {target_year}년 {target_qtr}분기)")
    
    db = SessionLocal()
    try:
        try:
            target_ciks = await fetch_all_13f_ciks(target_year, target_qtr)
        except Exception: return

        total = len(target_ciks)
        if total == 0: return

        # 🚨 [핵심 수정] 2개 -> 1개로 줄임 (메모리 보호)
        sem = asyncio.Semaphore(2) 

        async def worker(cik):
            async with sem:
                await asyncio.sleep(random.uniform(1.0, 2.0))
                try:
                    await update_institution_to_db(db, cik, is_featured=False)
                    gc.collect() # 🧹 작업 끝날 때마다 청소
                except Exception: pass

        tasks = [worker(cik) for cik in target_ciks]
        chunk_size = 20 # 50개 -> 20개로 줄임 (DB 부하 감소)
        
        for i in range(0, total, chunk_size):
            chunk = tasks[i : i + chunk_size]
            await asyncio.gather(*chunk)
            db.commit()
            print(f"🚀 진행률: {min(i + chunk_size, total)}/{total} 완료")
            gc.collect() # 🧹 청크 끝날 때마다 대청소

    except Exception as e:
        print(f"🔥 오류: {e}")
    finally:
        db.close()
        print("🏁 [Admin] 전체 업데이트 종료")

@router.post("/update/all")
async def update_all(background_tasks: BackgroundTasks, username: str = Depends(get_current_username)):
    background_tasks.add_task(run_crawler_process_all)
    return {"status": "success", "message": "⚠️ 안전 모드로 천천히 수집합니다. (메모리 보호)"}

# ... (유지보수 코드는 그대로) ...
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

@router.post("/reset-cache")
async def reset_cache(db: Session = Depends(get_db), username: str = Depends(get_current_username)):
    try:
        db.execute(text("UPDATE institutions SET description = NULL, ai_summary = NULL"))
        db.commit()
        return {"status": "success", "message": "🧹 초기화 완료"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@router.post("/fix-names")
async def fix_names(db: Session = Depends(get_db), username: str = Depends(get_current_username)):
    try:
        ghosts = db.query(Institution).filter((Institution.name == None) | (Institution.name == "")).count()
        return {"status": "success", "message": f"🔍 누락 데이터: {ghosts}개."}
    except Exception as e:
        return {"status": "error", "message": str(e)}