# fix_db.py
from sqlalchemy import text
from app.db.database import SessionLocal

def fix_database_schema():
    print("🚑 데이터베이스 종합 수리를 시작합니다...")
    db = SessionLocal()
    
    try:
        # ==========================================
        # 1. 기관(Institution) 테이블 수리
        # ==========================================
        print("🛠️ 1. Institutions 테이블 검사 중...")
        db.execute(text("ALTER TABLE institutions ADD COLUMN IF NOT EXISTS report_calendar_or_quarter VARCHAR;"))
        db.execute(text("ALTER TABLE institutions ADD COLUMN IF NOT EXISTS description TEXT;"))
        db.execute(text("ALTER TABLE institutions ADD COLUMN IF NOT EXISTS ai_summary TEXT;"))
        
        # ==========================================
        # 2. 보유종목(Holding) 테이블 수리 (여기가 문제였음!)
        # ==========================================
        print("🛠️ 2. Holdings 테이블 검사 중... (name_of_issuer 추가)")
        
        # 에러의 원인: name_of_issuer 컬럼 추가
        db.execute(text("ALTER TABLE holdings ADD COLUMN IF NOT EXISTS name_of_issuer VARCHAR;"))
        
        # 혹시 몰라 누락될 수 있는 다른 컬럼들도 싹 다 추가
        db.execute(text("ALTER TABLE holdings ADD COLUMN IF NOT EXISTS cusip VARCHAR;"))
        db.execute(text("ALTER TABLE holdings ADD COLUMN IF NOT EXISTS holding_type VARCHAR;"))
        db.execute(text("ALTER TABLE holdings ADD COLUMN IF NOT EXISTS change_rate FLOAT;"))
        
        db.commit()
        print("✅ 모든 테이블 수리 완료! 이제 진짜 됩니다.")
        
    except Exception as e:
        print(f"🔥 수리 실패: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    fix_database_schema()