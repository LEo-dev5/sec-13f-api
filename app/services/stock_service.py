import yfinance as yf
from sqlalchemy.orm import Session
from app.db.models import Holding

# 1. 특정 종목의 현재 주가를 가져오는 함수 (무료)
def get_stock_price(ticker: str) -> float:
    try:
        if not ticker: return 0.0
        # yfinance를 이용해 주가 조회 (무료)
        stock = yf.Ticker(ticker)
        history = stock.history(period="1d")
        if not history.empty:
            return float(history['Close'].iloc[-1])
        return 0.0
    except Exception:
        return 0.0

# 2. 전체 보유 종목 주가 업데이트
async def update_stock_prices(db: Session):
    print("📈 주가 일괄 업데이트 시작...")
    try:
        holdings = db.query(Holding).distinct(Holding.ticker).all()
        for holding in holdings:
            if holding.ticker:
                price = get_stock_price(holding.ticker)
                if price > 0:
                    db.query(Holding).filter(Holding.ticker == holding.ticker).update({"current_price": price})
        db.commit()
    except Exception as e:
        print(f"오류: {e}")