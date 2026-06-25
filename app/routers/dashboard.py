from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import get_db
from app.auth.rbac import role_required
from app.services.dashboard_service import DashboardService

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/metrics")
async def get_metrics(
    jd_id: int | None = None,
    current_user: dict = Depends(role_required("admin")),
    db: AsyncSession = Depends(get_db),
):
    service = DashboardService(db)
    return await service.get_metrics(jd_id=jd_id)
