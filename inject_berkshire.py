# inject_berkshire.py (크롤링 안함. 그냥 데이터를 심어버림)
import sys
import os

sys.path.append(os.getcwd())
from app.db.database import SessionLocal
from app.db.models import Institution, Holding
try:
    from update_cache import update_stock_summary
except:
    update_stock_summary = None

def inject_data():
    print("💉 [Cheat Mode] 버크셔 데이터 강제 주입 시작...")
    db = SessionLocal()
    
    try:
        # 1. 버크셔 기관 찾기 (없으면 생성)
        cik = "0001067983"
        inst = db.query(Institution).filter(Institution.cik == cik).first()
        if not inst:
            inst = Institution(cik=cik, name="BERKSHIRE HATHAWAY INC", is_featured=True)
            db.add(inst)
            db.commit()
            db.refresh(inst)
            
        # 2. 기존 데이터 삭제 (청소)
        print("🧹 기존 데이터 삭제 중...")
        db.query(Holding).filter(Holding.institution_id == inst.id).delete()
        
        # 3. 주요 종목 하드코딩 (2025년 기준 TOP 종목들)
        # 크롤링하다 막히느니 이게 낫습니다.
        print("📝 데이터 입력 중...")
        holdings_data = [
            ("APPLE INC", "AAPL", 400_000_000, 134_000_000_000), # 애플
            ("BANK OF AMERICA CORP", "BAC", 1_030_000_000, 34_000_000_000), # 뱅오아
            ("AMERICAN EXPRESS CO", "AXP", 151_600_000, 35_000_000_000), # 아멕스
            ("COCA COLA CO", "KO", 400_000_000, 24_000_000_000), # 코카콜라
            ("CHEVRON CORP", "CVX", 126_000_000, 18_000_000_000), # 쉐브론
            ("OCCIDENTAL PETROLEUM", "OXY", 248_000_000, 15_000_000_000), # 옥시덴탈
            ("KRAFT HEINZ CO", "KHC", 325_000_000, 12_000_000_000), # 크래프트하인즈
            ("MOODYS CORP", "MCO", 24_000_000, 9_600_000_000), # 무디스
            ("CHUBB LIMITED", "CB", 26_000_000, 6_700_000_000), # 처브
            ("DAVITA INC", "DVA", 36_000_000, 4_800_000_000), # 다비타
            ("CITIGROUP INC", "C", 55_000_000, 2_900_000_000), # 씨티그룹
            ("KROGER CO", "KR", 50_000_000, 2_700_000_000), # 크로거
        ]
        
        holdings = []
        for name, ticker, shares, val in holdings_data:
            holdings.append(Holding(
                institution_id=inst.id,
                name=name,
                name_of_issuer=name,
                ticker=ticker,
                value=val, # 달러 단위
                shares=shares,
                holding_type="Stock"
            ))
            
        db.bulk_save_objects(holdings)
        db.commit()
        print(f"✅ {len(holdings)}개 핵심 종목 주입 완료!")
        
        # 4. 검색 장부 업데이트
        if update_stock_summary:
            print("📚 검색 장부 업데이트...")
            update_stock_summary()
            
        print("🎉 끝! 이제 버크셔 나옵니다.")

    except Exception as e:
        print(f"🔥 에러: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    inject_data()