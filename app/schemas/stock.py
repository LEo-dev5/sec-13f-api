# app/schemas/stock.py
from pydantic import BaseModel
from typing import List, Optional

class Holding(BaseModel):
    name_of_issuer: str
    cusip: str
    value: int
    shares: int
    ssh_prnamt_type: str = "SH"
    change_rate: float = 0.0
    prev_shares: int = 0
    
    # 🚨 [필수 추가] 이 줄이 없어서 에러가 난 겁니다!
    holding_type: str = "Stock" 

class FilingResponse(BaseModel):
    cik: str
    institution_name: str
    report_date: str
    holdings: List[Holding]