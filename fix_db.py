# fix_db.py (VIP 칸 추가용)
import sys
import os
sys.path.append(os.getcwd())

from sqlalchemy import text
from app.db.database import SessionLocal

def fix_database_schema():
    print("🚑 데이터베이스 VIP 시스템 공사 중...")
    db = SessionLocal()
    
    try:
        # 1. is_featured 컬럼 추가 (없으면 생성)
        # BOOLEAN 타입으로 만들고 기본값은 False(일반)로 설정
        print("🛠️ Institution 테이블에 'is_featured' 추가 중...")
        db.execute(text("ALTER TABLE institutions ADD COLUMN IF NOT EXISTS is_featured BOOLEAN DEFAULT FALSE;"))
        
        db.commit()
        print("✅ DB 공사 완료! 이제 VIP 설정이 가능합니다.")
        
    except Exception as e:
        print(f"🔥 공사 실패: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    fix_database_schema()