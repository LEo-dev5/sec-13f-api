import asyncio
import os
import secrets
import random
from pathlib import Path
from fastapi import APIRouter, Request, Depends, HTTPException, status, BackgroundTasks
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from sqlalchemy import text, desc, func, cast, Date
from dotenv import load_dotenv
from datetime import timedelta, datetime

# 서비스 & DB 로직 (필수 import 복구 완료)
from app.db.database import get_db, SessionLocal
from app.db.models import Institution, Insight, Feedback, VisitLog
from app.services.sec_service import fetch_all_13f_ciks
from app.services.db_service import update_institution_to_db

load_dotenv()
router = APIRouter()
security = HTTPBasic()
templates = Jinja2Templates(directory="app/templates")

# 🌟 [TOP 20] 유명 기관 리스트 (빠른 업데이트용)
TOP_FUNDS = [
    ("0001067983", "BERKSHIRE HATHAWAY INC"), # 워렌 버핏
    ("0001350694", "BRIDGEWATER ASSOCIATES, LP"), # 레이 달리오
    ("0001649339", "SCION ASSET MANAGEMENT, LLC"), # 마이클 버리
    ("000102909", "VANGUARD GROUP INC"),
    ("0001364742", "BLACKROCK INC"),
    ("0001166559", "GATES BILL & MELINDA FOUNDATION"),
    ("0001103804", "Viking Global Investors Lp"),
    ("0001540531", "TIGER GLOBAL MANAGEMENT LLC"),
    ("0000902219", "BAILLIE GIFFORD & CO"),
    ("0001040273", "Citadel Advisors Llc"),
    ("0001336528", "Pershing Square Capital Management, L.P."),
    ("0001172435", "ARK INVESTMENT MANAGEMENT LLC"), # 캐시 우드
    ("0001423053", "SOROS FUND MANAGEMENT LLC"),
    ("0001541617", "Renaissance Technologies Llc"),
    ("0001569391", "DATAROMA"), 
]

# ====================================================
# 🔐 관리자 인증
# ====================================================
def get_current_username(credentials: HTTPBasicCredentials = Depends(security)):
    correct_username = os.getenv("ADMIN_USERNAME", "admin")
    correct_password = os.getenv("ADMIN_PASSWORD", "secret")
    
    is_correct_username = secrets.compare_digest(credentials.username, correct_username)
    is_correct_password = secrets.compare_digest(credentials.password, correct_password)
    
    if not (is_correct_username and is_correct_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="관리자 권한이 필요합니다.",
            headers={"WWW-Authenticate": "Basic"},
        )
    return credentials.username

# ====================================================
# 🖥️ 통합 대시보드
# ====================================================
@router.get("/")
async def admin_dashboard(request: Request, db: Session = Depends(get_db), username: str = Depends(get_current_username)):
    inst_count = db.query(Institution).count()
    insight_count = db.query(Insight).count()
    insight_list = db.query(Insight).order_by(desc(Insight.created_at)).all()
    feedback_list = db.query(Feedback).order_by(desc(Feedback.created_at)).all()
    
    # 최근 7일간 방문자 통계
    today = datetime.utcnow().date()
    seven_days_ago = today - timedelta(days=6)
    
    daily_stats = db.query(
        cast(VisitLog.timestamp, Date).label('date'),
        func.count(VisitLog.id).label('count')
    ).filter(
        VisitLog.timestamp >= seven_days_ago
    ).group_by(
        cast(VisitLog.timestamp, Date)
    ).order_by(
        cast(VisitLog.timestamp, Date)
    ).all()

    dates = []
    counts = []
    stats_dict = {stat.date: stat.count for stat in daily_stats}
    for i in range(7):
        d = seven_days_ago + timedelta(days=i)
        dates.append(d.strftime("%m-%d"))
        counts.append(stats_dict.get(d, 0))

    return templates.TemplateResponse("admin_dashboard.html", {
        "request": request,
        "username": username,
        "inst_count": inst_count,
        "insight_count": insight_count,
        "insights": insight_list,
        "feedbacks": feedback_list,
        "chart_dates": dates,
        "chart_counts": counts
    })

# ====================================================
# 🛠️ [기능 1] TOP 20 유명 기관 업데이트 (빠름)
# ====================================================
async def run_gurus_update():
    print("🚀 [Admin] 유명 기관(TOP 20) 업데이트 시작...")
    db = SessionLocal()
    try:
        for cik, name in TOP_FUNDS:
            print(f"🔄 Processing Guru: {name}")
            
            # DB에 없으면 이름 생성 (검색 되게 하려고)
            existing = db.query(Institution).filter(Institution.cik == cik).first()
            if not existing:
                new_inst = Institution(cik=cik, name=name, is_featured=True)
                db.add(new_inst)
                db.commit()

            # 데이터 업데이트
            await update_institution_to_db(db, cik, is_featured=True)
            await asyncio.sleep(1) # SEC 차단 방지 1초 휴식

    except Exception as e:
        print(f"🔥 Guru Update Failed: {e}")
    finally:
        db.close()
        print("🏁 [Admin] 유명 기관 업데이트 완료")

@router.post("/update/gurus")
async def update_gurus(background_tasks: BackgroundTasks, username: str = Depends(get_current_username)):
    background_tasks.add_task(run_gurus_update)
    return {"status": "success", "message": "TOP 20 기관 업데이트가 시작되었습니다."}


# ====================================================
# 🛠️ [기능 2] 전체(All) 데이터 대규모 수집 (느림)
# ====================================================
async def run_crawler_process_all():
    print("🏎️ [Admin] 전체 기관(All) 대규모 업데이트 시작...")
    db = SessionLocal()
    try:
        # 1. SEC에서 전체 명단 가져오기 (원래 로직 복구!)
        # (현재 시점이 2026년 1월이라면, 2025년 3분기 데이터가 최신입니다)
        try:
            target_ciks = await fetch_all_13f_ciks(2025, 3)
        except Exception as e:
            print(f"❌ 명단 다운로드 실패: {e}")
            return

        total = len(target_ciks)
        if total == 0:
            print("⚠️ 수집할 CIK가 없습니다.")
            return

        print(f"📋 총 {total}개 기관을 수집합니다. (오래 걸림)")

        # 2. 너무 많이 동시에 하면 차단되니, 2개씩 천천히
        sem = asyncio.Semaphore(2) 

        async def worker(cik):
            async with sem:
                # 랜덤 휴식 (SEC 차단 방지)
                await asyncio.sleep(random.uniform(1.0, 3.0))
                try:
                    # 전체 수집 시에는 is_featured=False
                    await update_institution_to_db(db, cik, is_featured=False)
                except Exception:
                    pass # 하나 실패해도 계속 진행

        # 3. 50개씩 끊어서 처리 (메모리 보호)
        tasks = [worker(cik) for cik in target_ciks]
        chunk_size = 50
        
        for i in range(0, total, chunk_size):
            chunk = tasks[i : i + chunk_size]
            await asyncio.gather(*chunk)
            db.commit() # 50개마다 저장
            print(f"🚀 전체 진행률: {min(i + chunk_size, total)}/{total} 완료")

    except Exception as e:
        print(f"🔥 전체 업데이트 중 치명적 오류: {e}")
    finally:
        db.close()
        print("🏁 [Admin] 전체 업데이트 종료")

@router.post("/update/all")
async def update_all(background_tasks: BackgroundTasks, username: str = Depends(get_current_username)):
    background_tasks.add_task(run_crawler_process_all)
    return {"status": "success", "message": "⚠️ 전체 데이터 수집을 시작합니다. (수천 개라 몇 시간 걸릴 수 있습니다!)"}


# ====================================================
# 🧹 유지보수
# ====================================================
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
        return {"status": "success", "message": "🧹 모든 설명 및 AI 분석 데이터가 초기화되었습니다."}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@router.post("/fix-names")
async def fix_names(db: Session = Depends(get_db), username: str = Depends(get_current_username)):
    try:
        ghosts = db.query(Institution).filter((Institution.name == None) | (Institution.name == "")).count()
        return {"status": "success", "message": f"🔍 현재 이름 누락 데이터: {ghosts}개."}
    except Exception as e:
        return {"status": "error", "message": str(e)}