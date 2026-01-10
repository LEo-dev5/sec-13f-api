# app/api/v1/endpoints/feedback.py

from fastapi import APIRouter, Depends, Form
from sqlalchemy.orm import Session
from app.db.database import get_db
from app.db.models import Feedback

router = APIRouter()

@router.post("/send")
async def send_feedback(
    content: str = Form(...),
    db: Session = Depends(get_db)
):
    try:
        new_feedback = Feedback(content=content)
        db.add(new_feedback)
        db.commit()
        return {"status": "success", "message": "소중한 의견 감사합니다! 🙇‍♂️"}
    except Exception as e:
        return {"status": "error", "message": str(e)}