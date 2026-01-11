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
from sqlalchemy import func, cast, Date 
from app.db.models import Institution, Insight, Feedback, VisitLog # VisitLog 추가
from datetime import timedelta, datetime

# 서비스 & DB 로직
from app.db.database import get_db, SessionLocal
from app.db.models import Institution, Insight, Feedback
from app.services.sec_service import fetch_all_13f_ciks
from app.services.db_service import update_institution_to_db

load_dotenv()
router = APIRouter()
security = HTTPBasic()
templates = Jinja2Templates(directory="app/templates")

TARGET_CIKS = ["0001067983", "0001350694", "0001649339"] # 버크셔, 브리지워터, 사이언

# ====================================================
# 🔐 [보안] 관리자 인증
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
# 🖥️ [화면] 통합 대시보드
# ====================================================
@router.get("/")
async def admin_dashboard(request: Request, db: Session = Depends(get_db), username: str = Depends(get_current_username)):
    inst_count = db.query(Institution).count()
    insight_count = db.query(Insight).count()
    insight_list = db.query(Insight).order_by(desc(Insight.created_at)).all()
    feedback_list = db.query(Feedback).order_by(desc(Feedback.created_at)).all()
    
    # 🚨 [추가] 최근 7일간 일별 방문자 수 집계
    today = datetime.utcnow().date()
    seven_days_ago = today - timedelta(days=6)
    
    # 날짜별로 그룹화해서 카운트 (SQL: SELECT date, count(*) FROM logs GROUP BY date)
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

    # 차트용 데이터 가공 (날짜 리스트, 숫자 리스트)
    dates = []
    counts = []
    
    # 데이터가 없는 날짜도 0으로 채우기 위한 로직
    stats_dict = {stat.date: stat.count for stat in daily_stats}
    for i in range(7):
        d = seven_days_ago + timedelta(days=i)
        dates.append(d.strftime("%m-%d")) # '01-11' 형식
        counts.append(stats_dict.get(d, 0))

    return templates.TemplateResponse("admin_dashboard.html", {
        "request": request,
        "username": username,
        "inst_count": inst_count,
        "insight_count": insight_count,
        "insights": insight_list,
        "feedbacks": feedback_list,
        "chart_dates": dates,   # 차트 X축
        "chart_counts": counts  # 차트 Y축
    })

# ====================================================
# 🛠️ [기능 1] 데이터 크롤링 & 업데이트 (여기가 빠져서 404가 떴던 겁니다!)
# ====================================================
async def run_crawler_process():
    print("🚀 [Admin] 핵심 기관(Gurus) 업데이트 시작...")
    db = SessionLocal()
    try:
        for cik in TARGET_CIKS:
            await update_institution_to_db(db, cik)
    except Exception as e:
        print(f"⚠️ [Admin] 오류: {e}")
    finally:
        db.close()
        print("🏁 [Admin] 핵심 기관 업데이트 완료")

async def run_crawler_process_all():
    print("🏎️ [Admin] 전체 기관(All) 대규모 업데이트 시작...")
    db = SessionLocal()
    try:
        try:
            target_ciks = await fetch_all_13f_ciks(2025, 3)
        except Exception:
            print("❌ 명단 다운로드 실패")
            return

        total = len(target_ciks)
        if total == 0: return

        sem = asyncio.Semaphore(2) 

        async def worker(cik):
            async with sem:
                await asyncio.sleep(random.uniform(1.0, 2.0))
                try:
                    await update_institution_to_db(db, cik, is_featured=False)
                except Exception:
                    pass

        tasks = [worker(cik) for cik in target_ciks]
        
        chunk_size = 50
        for i in range(0, total, chunk_size):
            chunk = tasks[i : i + chunk_size]
            await asyncio.gather(*chunk)
            db.commit()
            print(f"🚀 진행률: {min(i + chunk_size, total)}/{total} 완료")

    except Exception as e:
        print(f"🔥 전체 업데이트 중 오류: {e}")
    finally:
        db.close()
        print("🏁 [Admin] 전체 업데이트 종료")

@router.post("/update/gurus")
async def update_gurus(background_tasks: BackgroundTasks, username: str = Depends(get_current_username)):
    # 백그라운드에서 실행 (응답은 바로 줌)
    background_tasks.add_task(run_crawler_process)
    return {"status": "success", "message": "핵심 3대장 업데이트가 백그라운드에서 시작되었습니다!"}

@router.post("/update/all")
async def update_all(background_tasks: BackgroundTasks, username: str = Depends(get_current_username)):
    background_tasks.add_task(run_crawler_process_all)
    return {"status": "success", "message": "⚠️ 전체 데이터 수집이 시작되었습니다. (시간이 오래 걸립니다)"}

# ====================================================
# 🧹 [기능 2] 유지보수 & 피드백 관리
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
        return {"status": "success", "message": f"🔍 현재 이름 누락 데이터: {ghosts}개. (해당 페이지 접속 시 자동 복구됩니다)"}
    except Exception as e:
        return {"status": "error", "message": str(e)}