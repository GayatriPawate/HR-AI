import uuid
from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.db.base import get_db
from app.db.models import User, UserRole, Role, AuditLog
from app.auth.jwt_handler import create_access_token
from app.auth.password import hash_password, verify_password
from app.auth.rbac import get_current_user
from app.models.schemas import LoginRequest, LoginResponse, UserCreate

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=LoginResponse)
async def login(request: Request, payload: LoginRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(User).where(User.email == payload.email.lower().strip())
    )
    user = result.scalar_one_or_none()

    if not user or not verify_password(payload.password, user.password_hash):
        # Log failed attempt
        db.add(AuditLog(
            action="failed_login",
            entity_type="user",
            entity_id=payload.email,
            ip_address=request.client.host if request.client else None,
            outcome="failure",
            error_msg="Invalid credentials",
        ))
        await db.commit()
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account deactivated")

    # Get role
    role_result = await db.execute(
        select(Role)
        .join(UserRole, UserRole.role_id == Role.id)
        .where(UserRole.user_id == user.id)
    )
    role = role_result.scalar_one_or_none()
    role_name = role.name if role else "panel"

    token = create_access_token({"sub": user.id, "role": role_name, "email": user.email})

    # Audit
    db.add(AuditLog(
        user_id=user.id,
        user_role=role_name,
        action="login",
        entity_type="user",
        entity_id=user.id,
        ip_address=request.client.host if request.client else None,
        outcome="success",
    ))
    await db.commit()

    return LoginResponse(token=token, role=role_name, user_id=user.id, name=user.full_name)


@router.post("/register")
async def register(payload: UserCreate, db: AsyncSession = Depends(get_db)):
    # Check existing
    existing = await db.execute(select(User).where(User.email == payload.email.lower().strip()))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Email already registered")

    role_result = await db.execute(select(Role).where(Role.name == payload.role))
    role = role_result.scalar_one_or_none()
    if not role:
        raise HTTPException(status_code=400, detail=f"Role '{payload.role}' not found")

    user = User(
        id=str(uuid.uuid4()),
        email=payload.email.lower().strip(),
        password_hash=hash_password(payload.password),
        full_name=payload.full_name,
        department=payload.department,
        ms_email=payload.ms_email,
    )
    db.add(user)
    await db.flush()

    db.add(UserRole(user_id=user.id, role_id=role.id))
    await db.commit()

    return {"user_id": user.id, "email": user.email, "role": payload.role}


@router.get("/me")
async def me(current_user: dict = Depends(get_current_user)):
    return current_user
