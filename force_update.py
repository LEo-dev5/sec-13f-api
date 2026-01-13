# force_update.py
import asyncio
import sys
import os

# 경로 설정
sys.path.append(os.getcwd())

from app.services.db_service import update_institution_to_db
from app.db.database import SessionLocal
# update_cache가 있으면 가져오고, 없으면 패스 (유연하게)
try:
    from update_cache import update_stock_summary
except ImportError:
    update_stock_summary = None

async def manual_update():
    print("🚑 [Shell] 데이터 강제 업데이트 모드 시작...")
    db = SessionLocal()
    
    try:
        # 1. JP 모건 (JPMorgan Chase) - 0000019617
        print("🏦 JP모건 데이터 다운로드 중... (약 1~2분 소요)")
        await update_institution_to_db(db, "0000019617", is_featured=True)
        print("✅ JP모건 저장 완료!")

        # 2. 모건 스탠리 (Morgan Stanley) - 0000895421
        print("🏦 모건 스탠리 데이터 다운로드 중...")
        await update_institution_to_db(db, "0000895421", is_featured=True)
        print("✅ 모건 스탠리 저장 완료!")

        # 3. 골드만 삭스 (Goldman Sachs) - 0000886982
        print("🏦 골드만 삭스 데이터 다운로드 중...")
        await update_institution_to_db(db, "0000886982", is_featured=True)
        print("✅ 골드만 삭스 저장 완료!")

        # 4. 검색 장부 업데이트
        if update_stock_summary:
            print("📚 검색 장부(Cache) 갱신 중...")
            update_stock_summary()
            print("✅ 검색 인덱스 갱신 완료!")
        
        print("🎉 모든 작업 끝! 이제 사이트 들어가보세요.")

    except Exception as e:
        print(f"🔥 에러 발생: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    asyncio.run(manual_update())