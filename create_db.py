# create_db.py (프로젝트 최상위 폴더)
from app.db.database import Base, engine
from app.db.models import Institution, Holding

print("🗄️ 데이터베이스 테이블을 생성합니다...")
Base.metadata.create_all(bind=engine)
print("✅ '13f_data.db' 파일이 성공적으로 생성되었습니다!")