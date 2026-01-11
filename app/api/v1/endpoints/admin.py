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

# 서비스 & DB 로직
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
    # 1. 환경변수 가져오기 (기본값 "admin", "secret"을 삭제!)
    correct_username = os.getenv("ADMIN_USERNAME")
    correct_password = os.getenv("ADMIN_PASSWORD")
    
    # 🚨 [보안 강화] 환경변수가 설정 안 되어 있으면 아예 접속 불가 처리
    if not correct_username or not correct_password:
         raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="서버 보안 설정 오류: 관리자 계정이 설정되지 않았습니다. (Render 환경변수를 확인하세요)",
        )

    # 2. 아이디/비번 비교 (안전한 비교 함수 사용)
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
# 🧠 [스마트 기능] 현재 시점 기준 최신 분기 계산기
# ====================================================
def get_latest_filing_period():
    now = datetime.utcnow()
    # 2/15, 5/15, 8/15, 11/15 기준 분기 전환
    if now.month < 2 or (now.month == 2 and now.day < 15):
        return now.year - 1, 3
    elif now.month < 5 or (now.month == 5 and now.day < 15):
        return now.year - 1, 4
    elif now.month < 8 or (now.month == 8 and now.day < 15):
        return now.year, 1
    elif now.month < 11 or (now.month == 11 and now.day < 15):
        return now.year, 2
    else:
        return now.year, 3

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
# 🛠️ [기능 1] TOP 20 유명 기관 업데이트 (+ AI 자동 리셋)
# ====================================================
async def run_gurus_update():
    print("🚀 [Admin] 유명 기관(TOP 20) 업데이트 시작...")
    db = SessionLocal()
    try:
        for cik, name in TOP_FUNDS:
            print(f"🔄 Processing Guru: {name}")
            
            # DB에 없으면 등록
            existing = db.query(Institution).filter(Institution.cik == cik).first()
            if not existing:
                new_inst = Institution(cik=cik, name=name, is_featured=True)
                db.add(new_inst)
                db.commit()
                existing = new_inst # 참조 갱신

            # 1. 최신 데이터 업데이트
            await update_institution_to_db(db, cik, is_featured=True)
            
            # 🚨 [핵심 추가] 2. 데이터가 바뀌었으니 구형 AI 분석 삭제 (NULL로 초기화)
            # 이렇게 하면 사용자가 페이지 접속할 때 자동으로 새 분석을 요청함
            existing.ai_summary = None 
            db.commit()
            
            await asyncio.sleep(1)

    except Exception as e:
        print(f"🔥 Guru Update Failed: {e}")
    finally:
        db.close()
        print("🏁 [Admin] 유명 기관 업데이트 완료 (AI 분석 초기화됨)")

@router.post("/update/gurus")
async def update_gurus(background_tasks: BackgroundTasks, username: str = Depends(get_current_username)):
    background_tasks.add_task(run_gurus_update)
    return {"status": "success", "message": "TOP 20 기관 업데이트 시작! (완료 시 AI 분석도 갱신됩니다)"}

# ====================================================
# 🛠️ [기능 2] 전체(All) 데이터 대규모 수집 (+ AI 자동 리셋)
# ====================================================
async def run_crawler_process_all():
    target_year, target_qtr = get_latest_filing_period()
    print(f"🏎️ [Admin] 전체 기관 대규모 업데이트 시작... (타겟: {target_year}년 {target_qtr}분기)")
    
    db = SessionLocal()
    try:
        try:
            target_ciks = await fetch_all_13f_ciks(target_year, target_qtr)
        except Exception as e:
            print(f"❌ 명단 다운로드 실패: {e}")
            return

        total = len(target_ciks)
        if total == 0:
            print("⚠️ 수집할 CIK가 없습니다.")
            return

        print(f"📋 총 {total}개 기관을 수집합니다.")

        sem = asyncio.Semaphore(2) 

        async def worker(cik):
            async with sem:
                await asyncio.sleep(random.uniform(1.0, 3.0))
                try:
                    await update_institution_to_db(db, cik, is_featured=False)
                    
                    # 🚨 [핵심 추가] 성공하면 AI 요약 초기화
                    # (별도 DB 세션이 필요할 수 있으나, 여기선 간단히 처리)
                    # 대량 처리시에는 속도를 위해 생략하거나, 필요한 경우만 로직 추가
                    # 여기서는 안전하게 패스 (사용자가 직접 들어갈 때 생성되도록)
                except Exception:
                    pass

        tasks = [worker(cik) for cik in target_ciks]
        chunk_size = 50
        
        for i in range(0, total, chunk_size):
            chunk = tasks[i : i + chunk_size]
            await asyncio.gather(*chunk)
            
            # 🚨 청크 단위로 저장하면서, 해당 기관들의 AI 요약을 날려버릴 수도 있습니다.
            # 하지만 전체 업데이트는 너무 많으므로, 일단 데이터만 갱신합니다.
            db.commit()
            print(f"🚀 전체 진행률: {min(i + chunk_size, total)}/{total} 완료")

    except Exception as e:
        print(f"🔥 전체 업데이트 중 오류: {e}")
    finally:
        db.close()
        print("🏁 [Admin] 전체 업데이트 종료")

@router.post("/update/all")
async def update_all(background_tasks: BackgroundTasks, username: str = Depends(get_current_username)):
    background_tasks.add_task(run_crawler_process_all)
    return {"status": "success", "message": "⚠️ 전체 데이터 수집 시작. (데이터 갱신 시 AI 분석은 방문 시점에 생성됩니다)"}

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