# fix_berkshire.py
import asyncio
import sys
import os

# 현재 폴더 경로 추가
sys.path.append(os.getcwd())

from sqlalchemy import text
from app.db.database import SessionLocal
from app.services.db_service import update_institution_to_db
# 검색 장부 업데이트도 가져오기
try:
    from update_cache import update_stock_summary
except ImportError:
    update_stock_summary = None

async def fix_berkshire_only():
    print("🚑 [버크셔 해서웨이] 긴급 복구 수술 시작...")
    db = SessionLocal()
    
    try:
        # 1. 기존 0원짜리 잘못된 데이터 삭제 (Holding 테이블에서 버크셔꺼 싹 지움)
        print("🧹 기존의 0달러 데이터 삭제 중...")
        # 버크셔의 CIK: 0001067983
        # 기관 ID 찾기
        inst = db.execute(text("SELECT id FROM institutions WHERE cik = '0001067983'")).fetchone()
        
        if inst:
            inst_id = inst[0]
            # 보유 종목 삭제
            db.execute(text(f"DELETE FROM holdings WHERE institution_id = {inst_id}"))
            db.commit()
            print("🗑️ 쓰레기 데이터 청소 완료.")
        else:
            print("⚠️ 버크셔 기관 정보가 없어서 새로 생성합니다.")

        # 2. 데이터 새로 받아오기 (단독 실행이라 안 끊김)
        print("📡 SEC 서버에서 버크셔 데이터 다운로드 중... (최대 2분 소요)")
        # update_institution_to_db 함수가 내부적으로 fetch 하고 저장함
        await update_institution_to_db(db, "0001067983", is_featured=True)
        
        # 3. 결과 확인
        check_val = db.execute(text(
            f"SELECT sum(value) FROM holdings WHERE institution_id = {inst_id}"
        )).scalar()
        
        real_val = int(check_val) if check_val else 0
        print(f"💰 복구된 총 자산: ${real_val:,}")

        if real_val == 0:
            print("❌ [실패] 여전히 0달러입니다. SEC 서버 상태가 안 좋거나 차단되었습니다.")
        else:
            print("✅ [성공] 버크셔 자산이 정상 복구되었습니다!")
            
            # 4. 검색 장부에도 반영
            if update_stock_summary:
                print("📚 검색 장부 업데이트 중...")
                update_stock_summary()
                print("✅ 검색 기능 최신화 완료!")

    except Exception as e:
        print(f"🔥 수술 실패: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    asyncio.run(fix_berkshire_only())