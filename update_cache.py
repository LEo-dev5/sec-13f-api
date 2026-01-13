# update_cache.py
import sys
import os

# 현재 폴더를 파이썬 경로에 추가 (모듈 못 찾는 에러 방지)
sys.path.append(os.getcwd())

from sqlalchemy import func
from app.db.database import SessionLocal, engine
from app.db.models import Holding, StockSummary

def update_stock_summary():
    print("🚀 [Stock Summary] 데이터 압축을 시작합니다... (약 10~30초 소요)")
    db = SessionLocal()
    
    try:
        # 1. 요약 테이블(StockSummary)이 없으면 생성
        StockSummary.__table__.create(bind=engine, checkfirst=True)
        
        # 2. 기존 데이터 비우기 (중복 방지)
        db.query(StockSummary).delete()
        db.commit()
        
        # 3. 데이터 압축 (Group By)
        # 350만 개 행을 -> 종목별로 묶어서 합계 계산
        summary_query = (
            db.query(
                Holding.ticker,
                func.max(Holding.name).label("name"),
                func.sum(Holding.value).label("total_value"),
                func.count(Holding.institution_id).label("holder_count")
            )
            .filter(Holding.ticker != None)
            .filter(func.length(Holding.ticker) <= 5) # 이상한 티커 제외
            .group_by(Holding.ticker)
            .all()
        )
        
        print(f"✅ 총 {len(summary_query)}개의 종목으로 요약되었습니다.")
        
        # 4. DB에 저장
        summaries = []
        for row in summary_query:
            summaries.append(StockSummary(
                ticker=row.ticker,
                name=row.name,
                total_value=int(row.total_value) if row.total_value else 0, # int 변환 안전장치
                holder_count=row.holder_count
            ))
            
        db.bulk_save_objects(summaries)
        db.commit()
        print("🎉 [성공] 요약표 생성이 완료되었습니다!")
        
    except Exception as e:
        print(f"🔥 [에러] {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    update_stock_summary()