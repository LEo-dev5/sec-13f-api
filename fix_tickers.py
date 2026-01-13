# fix_tickers.py
from app.db.database import SessionLocal
from app.db.models import Holding
from sqlalchemy import text

def fix_tickers():
    db = SessionLocal()
    print("🚑 티커 긴급 복구 시작...")
    
    # 자주 찾는 인기 종목 매핑 (필요하면 여기에 계속 추가하세요!)
    mapping = {
        'NETFLIX': 'NFLX', 'ALPHABET': 'GOOGL', 'GOOGLE': 'GOOGL',
        'JPMORGAN': 'JPM', 'BERKSHIRE': 'BRK.B', 'VISA': 'V',
        'MASTERCARD': 'MA', 'UNITEDHEALTH': 'UNH', 'JOHNSON & JOHNSON': 'JNJ',
        'EXXON': 'XOM', 'PROCTER & GAMBLE': 'PG', 'HOME DEPOT': 'HD',
        'COSTCO': 'COST', 'WALMART': 'WMT', 'COCA COLA': 'KO',
        'PEPSICO': 'PEP', 'MCDONALDS': 'MCD', 'DISNEY': 'DIS',
        'ADOBE': 'ADBE', 'SALESFORCE': 'CRM', 'AMD': 'AMD',
        'INTEL': 'INTC', 'QUALCOMM': 'QCOM', 'CISCO': 'CSCO',
        # ... 여기에 원하는 종목 계속 추가
    }

    try:
        count = 0
        for name_keyword, ticker in mapping.items():
            # SQL: 이름에 키워드가 있고, 티커가 비어있는 놈들 일괄 업데이트
            query = text(f"""
                UPDATE holdings 
                SET ticker = :ticker 
                WHERE name ILIKE :pattern AND (ticker IS NULL OR ticker = '')
            """)
            result = db.execute(query, {"ticker": ticker, "pattern": f"%{name_keyword}%"})
            db.commit()
            print(f"✅ {name_keyword} -> {ticker} 복구 완료")
            count += 1
            
        print(f"🎉 총 {count}개 종목군의 티커를 복구했습니다!")
        
    except Exception as e:
        print(f"에러 발생: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    fix_tickers()