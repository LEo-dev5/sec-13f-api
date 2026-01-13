# update_cache.py
import sys
import os

# 현재 폴더 경로 추가 (Render 서버 호환용)
sys.path.append(os.getcwd())

from sqlalchemy import func, text
from app.db.database import SessionLocal, engine
from app.db.models import Holding, StockSummary

def update_stock_summary():
    print("🚀 [Render DB] 보유 종목 전체 스캔 시작...")
    db = SessionLocal()
    
    try:
        # 1. 기존 검색 장부 초기화
        StockSummary.__table__.create(bind=engine, checkfirst=True)
        db.query(StockSummary).delete()
        db.commit()
        
        # 2. DB에 있는 '모든' 종목 가져오기
        # 조건: 티커가 비어있지만 않으면 다 가져옴 (길이 제한 X, 공백 제한 X)
        summary_query = (
            db.query(
                Holding.ticker,
                func.max(Holding.name).label("name"),           # 이름
                func.sum(Holding.value).label("total_value"),   # 자산 규모
                func.count(Holding.institution_id).label("holder_count") # 보유 기관 수
            )
            .filter(Holding.ticker != None) # 티커가 NULL인 것만 제외
            .filter(Holding.ticker != "")   # 빈 문자열 제외
            .group_by(Holding.ticker)
            .all()
        )
        
        print(f"📦 DB에서 발견된 종목 수: {len(summary_query):,}개")
        
        # 3. 검색 장부에 등록 (최소한의 공백 정리만 함)
        summaries = []
        for row in summary_query:
            # DB에 있는 티커 그대로 사용 (공백만 제거)
            clean_ticker = row.ticker.strip().upper()
            
            # 이름이 없으면 티커로라도 대체
            clean_name = row.name if row.name else clean_ticker

            summaries.append(StockSummary(
                ticker=clean_ticker,
                name=clean_name,
                total_value=int(row.total_value) if row.total_value else 0,
                holder_count=row.holder_count
            ))
            
        # 4. 저장
        db.bulk_save_objects(summaries)
        db.commit()
        print(f"🎉 [완료] 우리 DB에 있는 {len(summaries):,}개 종목이 모두 검색됩니다!")
        
    except Exception as e:
        print(f"🔥 [에러] {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    update_stock_summary()