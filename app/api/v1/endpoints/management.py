"""
관리용 엔드포인트: SEC 데이터 동기화, 검색 인덱스 갱신 등
HTTP Basic Auth로 보호됩니다.
"""
import asyncio
import gc
import os
import random
import secrets
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from sqlalchemy.orm import Session
from sqlalchemy import func, text

from app.db.database import get_db, SessionLocal
from app.db.models import Institution, Holding, StockSummary
from app.services.sec_service import fetch_all_13f_ciks
from app.services.db_service import update_institution_to_db

router = APIRouter()
security = HTTPBasic()

# 주요 기관 CIK 목록
TOP_FUNDS = [
    ("0001067983", "BERKSHIRE HATHAWAY INC"),
    ("0001350694", "BRIDGEWATER ASSOCIATES, LP"),
    ("0001649339", "SCION ASSET MANAGEMENT, LLC"),
    ("000102909",  "VANGUARD GROUP INC"),
    ("0001364742", "BLACKROCK INC"),
    ("0000019617", "JPMORGAN CHASE & CO"),
    ("0000895421", "MORGAN STANLEY"),
    ("0000886982", "GOLDMAN SACHS GROUP INC"),
    ("0000070858", "BANK OF AMERICA CORP"),
    ("0001166559", "GATES BILL & MELINDA FOUNDATION"),
    ("0001103804", "Viking Global Investors Lp"),
    ("0001540531", "TIGER GLOBAL MANAGEMENT LLC"),
    ("0000902219", "BAILLIE GIFFORD & CO"),
    ("0001040273", "Citadel Advisors Llc"),
    ("0001336528", "Pershing Square Capital Management, L.P."),
    ("0001172435", "ARK INVESTMENT MANAGEMENT LLC"),
    ("0001423053", "SOROS FUND MANAGEMENT LLC"),
    ("0001541617", "Renaissance Technologies Llc"),
]


def get_current_username(credentials: HTTPBasicCredentials = Depends(security)):
    correct_username = os.getenv("ADMIN_USERNAME")
    correct_password = os.getenv("ADMIN_PASSWORD")
    if not correct_username or not correct_password:
        raise HTTPException(status_code=503, detail="서버 보안 설정 오류")

    is_correct = secrets.compare_digest(
        credentials.username, correct_username
    ) and secrets.compare_digest(credentials.password, correct_password)

    if not is_correct:
        raise HTTPException(
            status_code=401,
            detail="관리자 권한 필요",
            headers={"WWW-Authenticate": "Basic"},
        )
    return credentials.username


def _get_latest_filing_period():
    now = datetime.utcnow()
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


# ==========================================
# 1. 주요 기관 동기화
# ==========================================
async def _run_gurus_update():
    print("🚀 [Management] 주요 기관(TOP) 업데이트 시작...")
    db = SessionLocal()
    try:
        for cik, name in TOP_FUNDS:
            print(f"🔄 Processing: {name}")
            existing = db.query(Institution).filter(Institution.cik == cik).first()
            if not existing:
                new_inst = Institution(cik=cik, name=name, is_featured=True)
                db.add(new_inst)
                db.commit()

            await update_institution_to_db(db, cik, is_featured=True)
            gc.collect()
            await asyncio.sleep(2)
    except Exception as e:
        print(f"🔥 Guru Update Failed: {e}")
    finally:
        db.close()
        gc.collect()
        print("🏁 [Management] 주요 기관 업데이트 완료")


@router.post("/sync/gurus")
async def sync_gurus(
    background_tasks: BackgroundTasks,
    username: str = Depends(get_current_username),
):
    background_tasks.add_task(_run_gurus_update)
    return {"status": "accepted", "message": "주요 기관 동기화가 백그라운드에서 시작되었습니다."}


# ==========================================
# 2. 전체 기관 동기화
# ==========================================
async def _run_all_update():
    target_year, target_qtr = _get_latest_filing_period()
    print(f"🏎️ [Management] 전체 기관 업데이트 시작... ({target_year}년 {target_qtr}분기)")

    db = SessionLocal()
    try:
        target_ciks = await fetch_all_13f_ciks(target_year, target_qtr)
        total = len(target_ciks)
        if total == 0:
            return

        sem = asyncio.Semaphore(3)

        async def worker(cik):
            async with sem:
                await asyncio.sleep(random.uniform(1.0, 2.0))
                try:
                    await update_institution_to_db(db, cik, is_featured=False)
                    gc.collect()
                except Exception:
                    pass

        chunk_size = 50
        tasks = [worker(cik) for cik in target_ciks]
        for i in range(0, total, chunk_size):
            await asyncio.gather(*tasks[i : i + chunk_size])
            db.commit()
            print(f"🚀 진행률: {min(i + chunk_size, total)}/{total}")
            gc.collect()

    except Exception as e:
        print(f"🔥 오류: {e}")
    finally:
        db.close()
        print("🏁 [Management] 전체 업데이트 종료")


@router.post("/sync/all")
async def sync_all(
    background_tasks: BackgroundTasks,
    username: str = Depends(get_current_username),
):
    background_tasks.add_task(_run_all_update)
    return {"status": "accepted", "message": "전체 기관 동기화가 백그라운드에서 시작되었습니다."}


# ==========================================
# 3. 검색 인덱스 갱신
# ==========================================
@router.post("/rebuild-search-index")
async def rebuild_search_index(
    db: Session = Depends(get_db),
    username: str = Depends(get_current_username),
):
    try:
        db.query(StockSummary).delete()

        summary_query = (
            db.query(
                Holding.ticker,
                func.max(Holding.name).label("name"),
                func.sum(Holding.value).label("total_value"),
                func.count(Holding.institution_id).label("holder_count"),
            )
            .filter(Holding.ticker != None)
            .filter(func.length(Holding.ticker) <= 12)
            .group_by(Holding.ticker)
            .all()
        )

        summaries = [
            StockSummary(
                ticker=row.ticker.strip().upper(),
                name=row.name,
                total_value=int(row.total_value) if row.total_value else 0,
                holder_count=row.holder_count,
            )
            for row in summary_query
            if row.ticker and row.ticker.strip()
        ]

        db.bulk_save_objects(summaries)
        db.commit()

        return {"status": "success", "message": f"검색 인덱스 갱신 완료 (총 {len(summaries)}개 종목)"}
    except Exception as e:
        db.rollback()
        return {"status": "error", "message": str(e)}


# ==========================================
# 4. AI/위키 캐시 초기화
# ==========================================
@router.post("/reset-cache")
async def reset_cache(
    db: Session = Depends(get_db),
    username: str = Depends(get_current_username),
):
    try:
        db.execute(text("UPDATE institutions SET description = NULL, ai_summary = NULL"))
        db.commit()
        return {"status": "success", "message": "AI/위키 캐시 초기화 완료"}
    except Exception as e:
        return {"status": "error", "message": str(e)}
