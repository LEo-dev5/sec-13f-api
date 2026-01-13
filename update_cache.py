# update_cache.py (검색 범위 확장 버전)
import sys
import os

sys.path.append(os.getcwd())
from sqlalchemy import func
from app.db.database import SessionLocal, engine
from app.db.models import Holding, StockSummary

def update_stock_summary():
    print("🚀 [Render Server] 검색 인덱스 업데이트 시작...")
    db = SessionLocal()
    try:
        StockSummary.__table__.create(bind=engine, checkfirst=True)
        db.query(StockSummary).delete()
        db.commit()
        
        # 🚨 [중요] JPM, O, BRK.B 등을 위해 조건 완화 (12글자)
        summary_query = (
            db.query(
                Holding.ticker,
                func.max(Holding.name).label("name"),
                func.sum(Holding.value).label("total_value"),
                func.count(Holding.institution_id).label("holder_count")
            )
            .filter(Holding.ticker != None)
            .filter(func.length(Holding.ticker) <= 12) # 5 -> 12로 확장
            .group_by(Holding.ticker)
            .all()
        )
        
        summaries = []
        for row in summary_query:
            clean_ticker = row.ticker.strip().upper() if row.ticker else ""
            if clean_ticker:
                summaries.append(StockSummary(
                    ticker=clean_ticker,
                    name=row.name,
                    total_value=int(row.total_value) if row.total_value else 0,
                    holder_count=row.holder_count
                ))
            
        db.bulk_save_objects(summaries)
        db.commit()
        print(f"✅ 업데이트 완료! (총 {len(summaries)}개 종목)")
        
    except Exception as e:
        print(f"🔥 에러 발생: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    update_stock_summary()