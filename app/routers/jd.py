from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from groq import AsyncGroq

from app.db.base import get_db
from app.auth.rbac import role_required, require_any
from app.services.jd_service import JDService
from app.models.schemas import JDCreate
from app.utils.openai_client import get_openai_client

router = APIRouter(prefix="/jd", tags=["job-descriptions"])


@router.post("/create")
async def create_jd(
    payload: JDCreate,
    current_user: dict = Depends(role_required("admin")),
    db: AsyncSession = Depends(get_db),
    openai_client: AsyncGroq = Depends(get_openai_client),
):
    service = JDService(db, openai_client)
    result = await service.create_and_analyze(
        title=payload.title,
        raw_text=payload.raw_text,
        created_by=current_user["sub"],
    )
    return result


@router.get("/list")
async def list_jds(
    status: str | None = None,
    current_user: dict = Depends(require_any),
    db: AsyncSession = Depends(get_db),
    openai_client: AsyncGroq = Depends(get_openai_client),
):
    service = JDService(db, openai_client)
    return await service.list_jds(status=status)


@router.get("/{jd_id}")
async def get_jd(
    jd_id: int,
    current_user: dict = Depends(require_any),
    db: AsyncSession = Depends(get_db),
    openai_client: AsyncGroq = Depends(get_openai_client),
):
    service = JDService(db, openai_client)
    jd = await service.get_jd(jd_id)
    if not jd:
        raise HTTPException(status_code=404, detail="JD not found")
    return jd
