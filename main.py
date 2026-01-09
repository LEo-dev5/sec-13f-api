# main.py
from fastapi import FastAPI
from contextlib import asynccontextmanager
from app.api.v1.endpoints import sec, admin, home, search, stock
from app.services.ticker_service import load_sec_tickers

@asynccontextmanager
async def lifespan(app: FastAPI):
    # 시작될 때: 티커 다운로드
    await load_sec_tickers()
    yield
    # 꺼질 때: (할 거 없음)

app = FastAPI(lifespan=lifespan)


app.include_router(sec.router, prefix="/api/v1/sec", tags=["sec"])
app.include_router(admin.router, prefix="/api/v1/admin", tags=["admin"])
app.include_router(home.router, tags=["home"])
app.include_router(search.router, tags=["search"])
app.include_router(stock.router, tags=["stock"])