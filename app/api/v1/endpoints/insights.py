# app/api/v1/endpoints/insights.py

from fastapi import APIRouter, Depends, File, UploadFile, Form, Request, HTTPException
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from app.db.database import get_db
from app.db.models import Insight
import shutil
import os
import uuid

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")

UPLOAD_DIR = "app/static/uploads"

# 1. 글쓰기 페이지
@router.get("/admin/upload")
async def show_upload_page(request: Request):
    return templates.TemplateResponse("admin_upload.html", {"request": request})

# 2. 업로드 API
@router.post("/admin/upload")
async def upload_insight(
    title: str = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    try:
        file_extension = file.filename.split(".")[-1]
        unique_filename = f"{uuid.uuid4()}.{file_extension}"
        file_path = os.path.join(UPLOAD_DIR, unique_filename)
        
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
            
        web_path = f"/static/uploads/{unique_filename}"
        
        new_insight = Insight(title=title, image_url=web_path)
        db.add(new_insight)
        db.commit()
        
        return {"message": "업로드 성공!", "path": web_path}
    except Exception as e:
        return {"error": str(e)}

# 🚨 3. [추가] 삭제 API
@router.delete("/admin/{insight_id}")
async def delete_insight(insight_id: int, db: Session = Depends(get_db)):
    try:
        # DB에서 찾기
        insight = db.query(Insight).filter(Insight.id == insight_id).first()
        if not insight:
            raise HTTPException(status_code=404, detail="카드를 찾을 수 없습니다.")
        
        # 파일 삭제 (청소)
        # image_url 예시: "/static/uploads/abc.jpg" -> 실제경로 변환 필요
        if insight.image_url:
            filename = insight.image_url.split("/")[-1]
            file_path = os.path.join(UPLOAD_DIR, filename)
            if os.path.exists(file_path):
                os.remove(file_path) # 실제 파일 삭제
        
        # DB 삭제
        db.delete(insight)
        db.commit()
        
        return {"status": "success", "message": "삭제되었습니다."}
        
    except Exception as e:
        return {"status": "error", "message": str(e)}