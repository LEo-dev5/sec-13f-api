# app/api/v1/endpoints/admin.py
import asyncio
import os
import secrets
import random
from pathlib import Path
from fastapi import APIRouter, Request, Depends, HTTPException, status, BackgroundTasks
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.templating import Jinja2Templates
from dotenv import load_dotenv
from app.services.sec_service import fetch_all_13f_ciks


# 진짜 DB 로직
from app.db.database import SessionLocal
from app.services.db_service import update_institution_to_db

# 1. .env 파일 로드 (환경변수 가져오기)
load_dotenv()

router = APIRouter()
security = HTTPBasic() # 👈 브라우저 기본 로그인 기능

# 템플릿 경로 설정
BASE_DIR = Path(__file__).resolve().parent.parent.parent.parent.parent
TEMPLATE_DIR = BASE_DIR / "app" / "templates"
if not TEMPLATE_DIR.exists():
    TEMPLATE_DIR = Path("app/templates")

templates = Jinja2Templates(directory=str(TEMPLATE_DIR))

TARGET_CIKS = ["0001067983", "0001350694", "0001649339"]

# 🔐 [핵심] 관리자 인증 함수
# 이 함수를 통과 못하면 아예 페이지 진입 불가
def get_current_username(credentials: HTTPBasicCredentials = Depends(security)):
    # .env에서 아이디/비번 가져오기
    correct_username = os.getenv("ADMIN_USERNAME", "admin")
    correct_password = os.getenv("ADMIN_PASSWORD", "secret")
    
    # 안전한 문자열 비교 (해킹 방지용 비교 함수)
    is_correct_username = secrets.compare_digest(credentials.username, correct_username)
    is_correct_password = secrets.compare_digest(credentials.password, correct_password)
    
    if not (is_correct_username and is_correct_password):
        # 틀리면 401 에러와 함께 다시 로그인 창 띄움
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Basic"},
        )
    return credentials.username

# 1. 관리자 페이지 (이제 주소 뒤에 비밀번호 필요 없음!)
# Depends(get_current_username) 덕분에 접속하자마자 로그인 창이 뜹니다.
@router.get("/secret-manager")
async def admin_page(request: Request, username: str = Depends(get_current_username)):
    return templates.TemplateResponse("admin.html", {"request": request, "username": username})

# 2. 업데이트 API (여기도 보안 적용)
@router.post("/update_db")
async def update_database(background_tasks: BackgroundTasks, username: str = Depends(get_current_username)):
    background_tasks.add_task(run_crawler_process)
    return {"message": f"관리자({username}) 권한으로 업데이트를 시작합니다!"}

async def run_crawler_process():
    print("🚀 [Admin] 실제 DB 업데이트 작업을 시작합니다...")
    db = SessionLocal()
    try:
        for cik in TARGET_CIKS:
            await update_institution_to_db(db, cik)
    except Exception as e:
        print(f"⚠️ [Admin] 오류: {e}")
    finally:
        db.close()
        print("🏁 [Admin] 작업 종료")




async def run_crawler_process_all():
    print("🏎️ [Admin] 고속 전수 조사 시작! (동시 5개 처리, 딜레이 최소화)")
    
    db = SessionLocal()
    
    try:
        # 1. 명단 확보
        try:
            target_ciks = await fetch_all_13f_ciks(2025, 3)
        except Exception as e:
            print(f"❌ 명단 다운로드 실패: {e}")
            return

        total = len(target_ciks)
        if total == 0:
            print("⚠️ 수집할 기관이 없습니다. (SEC 차단 상태일 수 있음)")
            return

        try:
            target_ciks = await fetch_all_13f_ciks(2025, 3)
        except Exception as e:
            print(f"❌ 명단 다운로드 실패: {e}")
            return

        total = len(target_ciks)
        if total == 0:
            return

        # 🚨 [속도 조절] 5 -> 2 (욕심 버리기!)
        sem = asyncio.Semaphore(2) 

        async def worker(cik):
            async with sem:
                # 🚨 [속도 조절] 0.1초 -> 1.0~2.0초 (사람처럼 천천히)
                await asyncio.sleep(random.uniform(1.0, 2.0))
                
                try:
                    await update_institution_to_db(db, cik, is_featured=False)
                except Exception:
                    pass

        # 작업 스케줄링
        tasks = [worker(cik) for cik in target_ciks]
        
        # 진행률 표시 (50개씩 끊어서 저장)
        chunk_size = 50
        for i in range(0, total, chunk_size):
            chunk = tasks[i : i + chunk_size]
            await asyncio.gather(*chunk)
            
            # 중간 저장
            db.commit()
            # 진행률 로그도 깔끔하게 한 줄로
            print(f"🚀 진행 중: {min(i + chunk_size, total)}/{total} ({int((i+chunk_size)/total*100)}%) 완료")

    except Exception as e:
        print(f"🔥 치명적 오류: {e}")
    finally:
        db.close()
        print("🏁 [Admin] 전수 조사 종료")

# 2. 전수 조사 API
@router.post("/update_db_all")
async def update_database_all(background_tasks: BackgroundTasks, username: str = Depends(get_current_username)):
    background_tasks.add_task(run_crawler_process_all)
    return {"message": "⚠️ 전체 기관 업데이트 시작! (터미널 로그를 확인하세요)"}