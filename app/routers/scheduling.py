from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime

from app.db.base import get_db
from app.auth.rbac import role_required
from app.integrations.microsoft_graph.scheduling import GraphSchedulingService
from app.models.schemas import FindSlotsRequest, CreateEventRequest
from app.db.models import Candidate, JobDescription, User

router = APIRouter(prefix="/schedule", tags=["scheduling"])


@router.post("/find-slots")
async def find_slots(
    payload: FindSlotsRequest,
    current_user: dict = Depends(role_required("admin")),
    db: AsyncSession = Depends(get_db),
):
    service = GraphSchedulingService(db)
    try:
        slots = await service.find_meeting_times(
            attendee_emails=payload.panel_user_emails,
            date_from=datetime.fromisoformat(payload.date_from),
            date_to=datetime.fromisoformat(payload.date_to),
            duration_minutes=payload.duration_minutes,
            timezone=payload.timezone,
        )
        return {"available_slots": slots}
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e))


@router.post("/create-event")
async def create_event(
    payload: CreateEventRequest,
    current_user: dict = Depends(role_required("admin")),
    db: AsyncSession = Depends(get_db),
):
    # Get candidate name for subject
    cand_result = await db.execute(
        select(Candidate).where(Candidate.id == payload.candidate_id)
    )
    candidate = cand_result.scalar_one_or_none()
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")

    jd_result = await db.execute(
        select(JobDescription).where(JobDescription.id == payload.jd_id)
    )
    jd = jd_result.scalar_one_or_none()
    if not jd:
        raise HTTPException(status_code=404, detail="JD not found")

    subject = payload.subject or f"Interview: {candidate.full_name} — {jd.title}"
    body_html = f"""
    <h3>Interview Invitation</h3>
    <p><b>Candidate:</b> {candidate.full_name}</p>
    <p><b>Position:</b> {jd.title}</p>
    <p>Please join using the Teams link in this invitation.</p>
    """

    service = GraphSchedulingService(db)
    try:
        result = await service.create_calendar_event(
            candidate_id=payload.candidate_id,
            jd_id=payload.jd_id,
            attendee_emails=payload.panel_user_emails,
            subject=subject,
            body_html=body_html,
            start=datetime.fromisoformat(payload.start),
            end=datetime.fromisoformat(payload.end),
            timezone=payload.timezone,
            create_teams_meeting=payload.create_teams_meeting,
            organizer_id=current_user["sub"],
        )
        return result
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e))


@router.get("/list")
async def list_schedules(
    candidate_id: str | None = None,
    status: str | None = None,
    current_user: dict = Depends(role_required("admin")),
    db: AsyncSession = Depends(get_db),
):
    service = GraphSchedulingService(db)
    return await service.get_schedules(candidate_id=candidate_id, status=status)


@router.post("/{schedule_id}/cancel")
async def cancel_schedule(
    schedule_id: str,
    reason: str = "",
    current_user: dict = Depends(role_required("admin")),
    db: AsyncSession = Depends(get_db),
):
    service = GraphSchedulingService(db)
    success = await service.cancel_event(schedule_id, reason)
    if not success:
        raise HTTPException(status_code=404, detail="Schedule not found")
    return {"status": "cancelled"}
