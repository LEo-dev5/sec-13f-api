# app/services/db_service.py
from sqlalchemy.orm import Session
from app.db.models import Institution, Holding
from app.services.sec_service import fetch_latest_13f
from app.services.ticker_service import get_ticker_by_name

# 13F 보고서는 Value가 '$1000' 단위입니다. (100,000 = $100M = 1억 달러)
MIN_ASSETS_THRESHOLD = 100_000 

async def update_institution_to_db(db: Session, cik: str, is_featured: bool = False):
    try:
        filing_data = await fetch_latest_13f(cik)
    except Exception as e:
        return

    # 1. 자산 규모 필터링
    total_value = sum(h.value for h in filing_data.holdings)
    
    if not is_featured and total_value < MIN_ASSETS_THRESHOLD:
        print(f"📉 [Drop] {filing_data.institution_name}: ${total_value*1000:,} (기준 미달)")
        return

    print(f"🔄 [Save] {filing_data.institution_name}: ${total_value*1000:,} (저장 진행)")

    # 2. 기관 저장 (Upsert)
    inst = db.query(Institution).filter(Institution.cik == cik).first()
    if not inst:
        inst = Institution(cik=cik, name=filing_data.institution_name, is_featured=is_featured)
        db.add(inst)
        db.commit()
        db.refresh(inst)
    else:
        inst.name = filing_data.institution_name
        if is_featured: inst.is_featured = True 

    # 3. 보유 종목 업데이트
    try:
        # 기존 데이터 삭제
        db.query(Holding).filter(Holding.institution_id == inst.id).delete()
        
        # 🚨 [수정된 부분] 리스트 선언 추가 (이게 없어서 에러 날 예정이었음)
        new_holdings = [] 
        
        for h in filing_data.holdings:
            found_ticker = get_ticker_by_name(h.name_of_issuer)
            
            new_holdings.append(Holding(
                institution_id=inst.id,
                name=h.name_of_issuer,
                ticker=found_ticker,
                holding_type=h.holding_type, # Put/Call 저장
                shares=h.shares,
                value=h.value,
                change_rate=h.change_rate
            ))
        
        db.add_all(new_holdings)
        db.commit()
        
    except Exception as e:
        db.rollback()
        print(f"🔥 저장 실패: {e}")