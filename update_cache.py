from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, Index, BigInteger, Text, Float
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
    
    # 🌟 추가된 필드들 (AI 요약, 설명 등)
    description = Column(Text, nullable=True)  # 위키백과/GPT 기관 설명
    ai_summary = Column(Text, nullable=True)   # GPT가 분석한 3줄 요약
    
    # 관계 설정
    holdings = relationship("Holding", back_populates="institution")

# 2. 보유 종목 (Holding)
class Holding(Base):
    __tablename__ = "holdings"

    id = Column(Integer, primary_key=True, index=True)
    institution_id = Column(Integer, ForeignKey("institutions.id"))
    
    name_of_issuer = Column(String) # 원본 회사명
    name = Column(String)           # 정제된 종목명 (화면 표시용)
    ticker = Column(String, index=True) # 티커 (AAPL, TSLA...)
    
    cusip = Column(String)
    value = Column(BigInteger)      # 평가액 (금액이 커서 BigInteger 사용)
    shares = Column(BigInteger)     # 주식 수
    change_rate = Column(Float, nullable=True) # 전분기 대비 변동률
    holding_type = Column(String, nullable=True) # Call/Put/Stock 구분
    
    institution = relationship("Institution", back_populates="holdings")

# 3. [추가] 카드뉴스/인사이트 (Insight)
class Insight(Base):
    __tablename__ = "insights"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String)
    image_url = Column(String) # 이미지 경로 (/static/uploads/...)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

# 4. [추가] 사용자 피드백 (Feedback)
class Feedback(Base):
    __tablename__ = "feedbacks"

    id = Column(Integer, primary_key=True, index=True)
    content = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

# 5. [추가] 방문자 로그 (VisitLog)
class VisitLog(Base):
    __tablename__ = "visit_logs"

    id = Column(Integer, primary_key=True, index=True)
    ip_address = Column(String)
    path = Column(String)
    timestamp = Column(DateTime(timezone=True), server_default=func.now())

# 6. [🚀 속도 개선 핵심] 종목 요약표 (StockSummary)
class StockSummary(Base):
    __tablename__ = "stock_summaries"

    ticker = Column(String, primary_key=True, index=True) # 티커 (PK)
    name = Column(String)       # 종목명
    total_value = Column(BigInteger) # 총 보유 평가액 합계
    holder_count = Column(Integer)   # 보유 기관 수
    
    # 검색 속도를 위한 인덱스
    __table_args__ = (
        Index('idx_stock_summary_name', 'name'),
    )