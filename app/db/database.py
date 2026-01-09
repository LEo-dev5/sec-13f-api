# app/db/database.py
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

# 1. SQLite 데이터베이스 파일 경로 지정
# ./13f_data.db 라는 파일이 프로젝트 루트에 생깁니다.
SQLALCHEMY_DATABASE_URL = "sqlite:///./13f_data.db"

# 2. 엔진 생성 (SQLite는 한 번에 한 쓰레드만 접근 가능하므로 check_same_thread=False 필요)
engine = create_engine(
    SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
)

# 3. 세션(접속기) 생성기
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# 4. 모델들이 상속받을 기본 클래스
Base = declarative_base()

# 5. DB 세션을 가져오는 의존성 함수 (FastAPI에서 사용)
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()