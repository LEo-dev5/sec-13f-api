# fix_db.py
import sys
import os
sys.path.append(os.getcwd())

from sqlalchemy import text
from app.db.database import SessionLocal

def fix_database_schema():
    print("🚑 데이터베이스 긴급 수리 중...")
    db = SessionLocal()
    
    try:
        # 1. VIP 표시 컬럼 추가
        print("🛠️ Institutions 테이블에 'is_featured' 칸 뚫는 중...")
        db.execute(text("ALTER TABLE institutions ADD COLUMN IF NOT EXISTS is_featured BOOLEAN DEFAULT FALSE;"))
        
        db.commit()
        print("✅ DB 수리 완료!")
        
    except Exception as e:
        print(f"🔥 수리 실패: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    fix_database_schema()