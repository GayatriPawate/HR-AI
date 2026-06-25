from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.db.base import get_db
from app.auth.rbac import role_required
from app.db.models import User, UserRole, Role

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/list")
async def list_users(
    current_user: dict = Depends(role_required("admin")),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(User, Role)
        .join(UserRole, UserRole.user_id == User.id)
        .join(Role, Role.id == UserRole.role_id)
    )
    rows = result.all()
    return [
        {
            "id": u.id,
            "email": u.email,
            "full_name": u.full_name,
            "department": u.department,
            "role": r.name,
            "is_active": u.is_active,
            "ms_email": u.ms_email,
            "created_at": u.created_at.isoformat() if u.created_at else None,
        }
        for u, r in rows
    ]


@router.patch("/{user_id}/deactivate")
async def deactivate_user(
    user_id: str,
    current_user: dict = Depends(role_required("admin")),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if user.id == current_user["sub"]:
        raise HTTPException(status_code=400, detail="Cannot deactivate yourself")
    user.is_active = False
    await db.commit()
    return {"status": "deactivated", "user_id": user_id}


@router.patch("/{user_id}/activate")
async def activate_user(
    user_id: str,
    current_user: dict = Depends(role_required("admin")),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    user.is_active = True
    await db.commit()
    return {"status": "activated", "user_id": user_id}


@router.get("/panel-members")
async def list_panel_members(
    current_user: dict = Depends(role_required("admin")),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(User)
        .join(UserRole, UserRole.user_id == User.id)
        .join(Role, Role.id == UserRole.role_id)
        .where(Role.name == "panel", User.is_active == True)
    )
    members = result.scalars().all()
    return [
        {"id": u.id, "full_name": u.full_name, "email": u.email,
         "ms_email": u.ms_email, "department": u.department}
        for u in members
    ]
