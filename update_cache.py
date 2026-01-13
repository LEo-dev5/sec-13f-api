# update_cache.py
import sys
import os

# 현재 폴더 경로 추가 (Render 서버 호환용)
sys.path.append(os.getcwd())

from sqlalchemy import func, desc
from app.db.database import SessionLocal, engine
from app.db.models import Holding, StockSummary

def update_stock_summary():
    print("🚀 [ALL-PASS] 기관이 보유한 '모든 종목'을 인덱싱합니다...")
    db = SessionLocal()
    
    try:
        # 1. 요약 테이블 초기화 (싹 비우기)
        StockSummary.__table__.create(bind=engine, checkfirst=True)
        db.query(StockSummary).delete()
        db.commit()
        
        # 2. 모든 보유 종목 긁어모으기 (조건 삭제!)
        # - 티커가 널(Null)만 아니면 다 가져옵니다.
        # - JPM, O, BRK.B 등 특이한 티커도 다 포함됩니다.
        summary_query = (
            db.query(
                Holding.ticker,
                func.max(Holding.name).label("name"),           # 이름은 아무거나 하나
                func.sum(Holding.value).label("total_value"),   # 총 자산 합계
                func.count(Holding.institution_id).label("holder_count") # 보유 기관 수
            )
            .filter(Holding.ticker != None)       # 티커 없는 유령 데이터만 제외
            .filter(Holding.ticker != "")         # 빈 문자열 제외
            .group_by(Holding.ticker)             # 티커별로 뭉치기
            .all()
        )
        
        print(f"📦 수집된 종목 수: {len(summary_query)}개")
        
        # 3. DB에 저장 (공백 제거 등 최소한의 청소만 함)
        summaries = []
        for row in summary_query:
            # " JPM " -> "JPM" (앞뒤 공백만 제거)
            clean_ticker = row.ticker.strip().upper()
            
            # 간혹 티커가 너무 긴 이상한 데이터(50자 이상)는 DB 에러 유발하므로 컷
            if len(clean_ticker) > 0 and len(clean_ticker) < 20:
                summaries.append(StockSummary(
                    ticker=clean_ticker,
                    name=row.name,
                    total_value=int(row.total_value) if row.total_value else 0,
                    holder_count=row.holder_count
                ))
            
        # 대량 저장 (Bulk Insert)
        db.bulk_save_objects(summaries)
        db.commit()
        print(f"🎉 [완료] 총 {len(summaries)}개의 종목이 검색 가능해졌습니다!")
        
    except Exception as e:
        print(f"🔥 [에러] {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    update_stock_summary()