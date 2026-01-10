# create_insight_table.py
from app.db.database import engine, Base
from app.db.models import Insight

print("🔨 인사이트(Insight) 테이블을 생성합니다...")
Base.metadata.create_all(bind=engine)
print("✅ 성공! 'insights' 테이블이 생성되었습니다.")

