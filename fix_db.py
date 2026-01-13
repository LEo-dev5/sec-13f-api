# fix_db.py
from sqlalchemy import text
from app.db.database import SessionLocal

def fix_database_schema():
    print("🚑 데이터베이스 긴급 수리를 시작합니다...")
    db = SessionLocal()
    
    try:
        # 1. 누락된 컬럼 강제 추가 (report_calendar_or_quarter)
        print("1. report_calendar_or_quarter 컬럼 추가 중...")
        db.execute(text("ALTER TABLE institutions ADD COLUMN IF NOT EXISTS report_calendar_or_quarter VARCHAR;"))
        
        # 2. 혹시 몰라 description, ai_summary도 확인 (없으면 추가됨)
        print("2. description / ai_summary 컬럼 확인 중...")
        db.execute(text("ALTER TABLE institutions ADD COLUMN IF NOT EXISTS description TEXT;"))
        db.execute(text("ALTER TABLE institutions ADD COLUMN IF NOT EXISTS ai_summary TEXT;"))
        
        db.commit()
        print("✅ 수리 완료! 이제 서버가 정상 작동할 것입니다.")
        
    except Exception as e:
        print(f"🔥 수리 실패: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    fix_database_schema()