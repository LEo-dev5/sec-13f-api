# add_gurus.py (프로젝트 최상위 폴더에 위치)
import asyncio
from app.db.database import SessionLocal
from app.services.db_service import update_institution_to_db

# 버크셔(버핏), 사이언(버리), 브리지워터(달리오) CIK
GURU_CIKS = ["0001067983", "0001649339", "0001350694"]

async def init_gurus():
    print("🚀 [System] 유명 투자자 3인방 데이터를 긴급 공수합니다...")
    
    db = SessionLocal()
    try:
        for cik in GURU_CIKS:
            print(f"📥 데이터 수집 시도: CIK {cik}...")
            # is_featured=True로 설정하여 'Guru' 등급으로 저장
            await update_institution_to_db(db, cik, is_featured=True)
            print(f"✅ 수집 완료: {cik}")
            
    except Exception as e:
        print(f"🔥 에러 발생: {e}")
    finally:
        db.close()
        print("🎉 [Complete] 모든 작업이 끝났습니다! 이제 메인 페이지를 새로고침하세요.")

if __name__ == "__main__":
    asyncio.run(init_gurus())