import yfinance as yf

# 특정 종목의 현재 주가를 가져오는 함수 (무료)
def get_stock_price(ticker: str) -> float:
    try:
        if not ticker: return 0.0
        stock = yf.Ticker(ticker)
        history = stock.history(period="1d")
        if not history.empty:
            return float(history['Close'].iloc[-1])
        return 0.0
    except Exception:
        return 0.0