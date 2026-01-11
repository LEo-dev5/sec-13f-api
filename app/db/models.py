from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Text, BigInteger, Boolean # 👈 BigInteger 추가!
from sqlalchemy.orm import relationship
from app.db.database import Base
from datetime import datetime

class Institution(Base):
    __tablename__ = "institutions"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    cik = Column(String, unique=True, index=True)
    description = Column(Text, nullable=True)
    ai_summary = Column(Text, nullable=True) 
    is_featured = Column(Boolean, default=False) # (Boolean이 없다면 import 필요, 없어도 무관)

    holdings = relationship("Holding", back_populates="institution")

class Holding(Base):
    __tablename__ = "holdings"

    id = Column(Integer, primary_key=True, index=True)
    institution_id = Column(Integer, ForeignKey("institutions.id"))
    
    name = Column(String)
    ticker = Column(String)
    holding_type = Column(String)
    
    # 🚨 [핵심 수정] Integer -> BigInteger로 변경
    # 주식 수와 평가액은 21억을 넘을 수 있으므로 큰 통을 써야 합니다.
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