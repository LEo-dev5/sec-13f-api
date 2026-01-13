# app/db/models.py (최종 수정본)
from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, Index, BigInteger, Text, Float, Boolean
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db.database import Base

# 1. 기관 (Institution)
class Institution(Base):
    __tablename__ = "institutions"

    id = Column(Integer, primary_key=True, index=True)
    cik = Column(String, unique=True, index=True)
    name = Column(String)
    report_calendar_or_quarter = Column(String)
    
    # 🌟 [필수] VIP 기관 표시 (이게 없어서 아까 에러남)
    is_featured = Column(Boolean, default=False)

    # 설명 및 AI 요약
    description = Column(Text, nullable=True)
    ai_summary = Column(Text, nullable=True)
    
    # 관계 설정
    holdings = relationship("Holding", back_populates="institution")

# 2. 보유 종목 (Holding)
class Holding(Base):
    __tablename__ = "holdings"

    id = Column(Integer, primary_key=True, index=True)
    institution_id = Column(Integer, ForeignKey("institutions.id"))
    
    name_of_issuer = Column(String) 
    name = Column(String)           
    ticker = Column(String, index=True)
    
    cusip = Column(String)
    value = Column(BigInteger)      
    shares = Column(BigInteger)     
    change_rate = Column(Float, nullable=True) 
    holding_type = Column(String, nullable=True) 
    
    institution = relationship("Institution", back_populates="holdings")

# 3. 카드뉴스 (Insight)
class Insight(Base):
    __tablename__ = "insights"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String)
    image_url = Column(String)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

# 4. 피드백 (Feedback)
class Feedback(Base):
    __tablename__ = "feedbacks"

    id = Column(Integer, primary_key=True, index=True)
    content = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

# 5. 방문자 로그 (VisitLog)
class VisitLog(Base):
    __tablename__ = "visit_logs"

    id = Column(Integer, primary_key=True, index=True)
    ip_address = Column(String)
    path = Column(String)
    timestamp = Column(DateTime(timezone=True), server_default=func.now())

# 6. 종목 요약표 (StockSummary)
class StockSummary(Base):
    __tablename__ = "stock_summaries"

    ticker = Column(String, primary_key=True, index=True)
    name = Column(String)       
    total_value = Column(BigInteger)
    holder_count = Column(Integer)   
    
    __table_args__ = (
        Index('idx_stock_summary_name', 'name'),
    )