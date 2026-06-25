from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional

from app.db.base import get_db
from app.auth.rbac import role_required, require_any  # require_any = role_required("admin","panel")
from app.services.availability_service import AvailabilityService
from app.models.schemas import SlotCreate, SlotBulkCreate, SlotBookRequest

router = APIRouter(prefix="/availability", tags=["availability"])


# ── Admin: post slots ─────────────────────────────────────────

@router.post("/slots", summary="Admin: create one or more availability slots for a panel member")
async def create_slots(
    payload: SlotBulkCreate,
    current_user: dict = Depends(role_required("admin")),
    db: AsyncSession = Depends(get_db),
):
    service = AvailabilityService(db)
    try:
        created = await service.create_slots(
            panel_user_id=payload.panel_user_id,
            slots=payload.slots,
            jd_id=payload.jd_id,
            created_by=current_user["sub"],
        )
        return {"created": len(created), "slots": created}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/slots/{slot_id}", summary="Admin: remove an unbooked slot")
async def delete_slot(
    slot_id: str,
    current_user: dict = Depends(role_required("admin")),
    db: AsyncSession = Depends(get_db),
):
    service = AvailabilityService(db)
    try:
        ok = await service.delete_slot(slot_id)
        if not ok:
            raise HTTPException(status_code=404, detail="Slot not found")
        return {"deleted": slot_id}
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))


# ── List available slots (admin or panel) ─────────────────────

@router.get("/slots", summary="List slots — filter by panel member, JD, or status")
async def list_slots(
    panel_user_id: Optional[str] = Query(None),
    jd_id: Optional[int] = Query(None),
    status: Optional[str] = Query(None),
    current_user: dict = Depends(require_any),
    db: AsyncSession = Depends(get_db),
):
    service = AvailabilityService(db)
    # Panel members can only see their own slots
    if current_user.get("role") == "panel":
        panel_user_id = current_user["sub"]
    return await service.list_slots(panel_user_id=panel_user_id, jd_id=jd_id, status=status)


# ── Admin: book slot on behalf of a candidate ─────────────────

@router.post("/book", summary="Admin: book a slot for a candidate (atomic, race-safe)")
async def book_slot(
    payload: SlotBookRequest,
    current_user: dict = Depends(role_required("admin")),
    db: AsyncSession = Depends(get_db),
):
    service = AvailabilityService(db)
    try:
        booking = await service.book_slot(
            slot_id=payload.slot_id,
            candidate_id=payload.candidate_id,
            jd_id=payload.jd_id,
            booked_by=current_user["sub"],
            interview_id=payload.interview_id,
            notes=payload.notes,
        )
        return booking
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))


# ── List bookings ─────────────────────────────────────────────

@router.get("/bookings", summary="List all bookings, optionally filtered")
async def list_bookings(
    panel_user_id: Optional[str] = Query(None),
    jd_id: Optional[int] = Query(None),
    candidate_id: Optional[str] = Query(None),
    current_user: dict = Depends(require_any),
    db: AsyncSession = Depends(get_db),
):
    service = AvailabilityService(db)
    if current_user.get("role") == "panel":
        panel_user_id = current_user["sub"]
    return await service.list_bookings(
        panel_user_id=panel_user_id,
        jd_id=jd_id,
        candidate_id=candidate_id,
    )


# ── Cancel a booking ──────────────────────────────────────────

@router.delete("/bookings/{booking_id}", summary="Admin: cancel a booking and free the slot")
async def cancel_booking(
    booking_id: str,
    current_user: dict = Depends(role_required("admin")),
    db: AsyncSession = Depends(get_db),
):
    service = AvailabilityService(db)
    ok = await service.cancel_booking(booking_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Booking not found")
    return {"cancelled": booking_id}
