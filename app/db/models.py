# app/db/models.py
from sqlalchemy import Column, Integer, String, Date, Float, ForeignKey, Text, Boolean, DateTime
from datetime import datetime
from sqlalchemy.orm import relationship
from .database import Base

class Institution(Base):
    __tablename__ = "institutions"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    cik = Column(String, unique=True, index=True)
    is_featured = Column(Boolean, default=False)
    ai_summary = Column(Text, nullable=True)
    description = Column(Text, nullable=True)
    holdings = relationship("Holding", back_populates="owner", cascade="all, delete-orphan")

class Holding(Base):
    __tablename__ = "holdings"
    id = Column(Integer, primary_key=True, index=True)
    institution_id = Column(Integer, ForeignKey("institutions.id"))
    
    name = Column(String)
    ticker = Column(String, index=True)
    
    # [NEW] 유형 컬럼 추가 (Stock / Put / Call)
    holding_type = Column(String, default="Stock")
    
    shares = Column(Integer)
    value = Column(Integer)
    change_rate = Column(Float)
    
    owner = relationship("Institution", back_populates="holdings")

class Insight(Base):
    __tablename__ = "insights"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, index=True)       # 카드 뉴스 제목 (검색용/Alt 텍스트)
    image_url = Column(String)               # 이미지 파일 경로 (예: /static/uploads/card1.jpg)
    created_at = Column(DateTime, default=datetime.utcnow) # 작성일 (최신순 정렬용)

class Feedback(Base):
    __tablename__ = "feedbacks"

    id = Column(Integer, primary_key=True, index=True)
    content = Column(String)  # 피드백 내용
    created_at = Column(DateTime, default=datetime.utcnow)