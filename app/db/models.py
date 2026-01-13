from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Text, BigInteger, Boolean # 👈 BigInteger 추가!
from sqlalchemy.orm import relationship
from app.db.database import Base
from datetime import datetime

class Institution(Base):
    __tablename__ = "institutions"
    # ... (기존 코드 유지) ...
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    cik = Column(String, unique=True, index=True)
    description = Column(Text, nullable=True)
    ai_summary = Column(Text, nullable=True) 
    is_featured = Column(Boolean, default=False) # (Boolean import 필요하면 추가)

    holdings = relationship("Holding", back_populates="institution")

class Holding(Base):
    __tablename__ = "holdings"

    id = Column(Integer, primary_key=True, index=True)
    
    # 1. 특정 기관의 종목 리스트를 불러올 때 속도 개선 (상세페이지 로딩)
    institution_id = Column(Integer, ForeignKey("institutions.id"), index=True) # 👈 index 추가!
    
    name = Column(String)
    
    # 2. 'TSLA' 검색 시 미친 듯이 빨라지게 하는 핵심 설정 (검색 결과 개선)
    ticker = Column(String, index=True) # 👈 index 추가!
    
    holding_type = Column(String)
    
    # 🚨 BigInteger 유지
    shares = Column(BigInteger) 
    value = Column(BigInteger)
    
    change_rate = Column(Float)

    institution = relationship("Institution", back_populates="holdings")

class Insight(Base):
    __tablename__ = "insights"
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String)
    image_url = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)


class Feedback(Base):
    __tablename__ = "feedbacks"
    id = Column(Integer, primary_key=True, index=True)
    content = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)

class VisitLog(Base):
    __tablename__ = "visit_logs"

    id = Column(Integer, primary_key=True, index=True)
    ip_address = Column(String)
    path = Column(String)
    # 3. 날짜별 방문자 수 통계를 낼 때 빨라집니다.
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)

class StockSummary(Base):
    __tablename__ = "stock_summaries"

    ticker = Column(String, primary_key=True, index=True) # 티커 (PK)
    name = Column(String)       # 종목명 (대표 이름)
    total_value = Column(BigInteger) # 총 보유 평가액 합계
    holder_count = Column(Integer)   # 보유 기관 수
    
    # 검색 속도를 위한 인덱스 (검색할 때 이름도 봅니다)
    __table_args__ = (
        Index('idx_stock_summary_name', 'name'),
    )