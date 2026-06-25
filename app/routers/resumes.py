from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from groq import AsyncGroq

from app.db.base import get_db
from app.auth.rbac import role_required
from app.services.resume_service import ResumeService
from app.utils.openai_client import get_openai_client

router = APIRouter(prefix="/resumes", tags=["resumes"])


@router.post("/upload")
async def upload_resumes(
    files: List[UploadFile] = File(...),
    jd_id: Optional[int] = Form(None),
    current_user: dict = Depends(role_required("admin")),
    db: AsyncSession = Depends(get_db),
    openai_client: AsyncGroq = Depends(get_openai_client),
):
    if not files:
        raise HTTPException(status_code=400, detail="No files provided")

    service = ResumeService(db, openai_client)
    results = []
    for file in files:
        file_bytes = await file.read()
        result = await service.ingest_file(
            filename=file.filename,
            file_bytes=file_bytes,
            uploaded_by=current_user["sub"],
            jd_id=jd_id,
        )
        results.append(result)

    success_count = sum(1 for r in results if r["status"] == "success")
    return {
        "total": len(results),
        "success": success_count,
        "failed": len(results) - success_count,
        "results": results,
    }


@router.get("/candidates")
async def list_candidates(
    jd_id: Optional[int] = None,
    limit: int = 100,
    offset: int = 0,
    current_user: dict = Depends(role_required("admin")),
    db: AsyncSession = Depends(get_db),
    openai_client: AsyncGroq = Depends(get_openai_client),
):
    service = ResumeService(db, openai_client)
    candidates = await service.get_candidates(jd_id=jd_id, limit=limit, offset=offset)
    return {"candidates": candidates, "count": len(candidates)}
