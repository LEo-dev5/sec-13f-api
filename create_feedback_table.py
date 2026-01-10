# create_feedback_table.py
from app.db.database import engine, Base
from app.db.models import Feedback

print("🔨 피드백(Feedback) 테이블을 생성합니다...")
Base.metadata.create_all(bind=engine)
print("✅ 성공! 'feedbacks' 테이블이 생성되었습니다.")