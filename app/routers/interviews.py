from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from groq import AsyncGroq
from typing import Optional

from app.db.base import get_db
from app.auth.rbac import role_required, require_any
from app.services.interview_service import InterviewService
from app.models.schemas import FeedbackSubmit, PanelAssignRequest, InterviewCreate
from app.utils.openai_client import get_openai_client
from app.agents.email_agent import EmailInviteAgent

router = APIRouter(prefix="/interviews", tags=["interviews"])


class EmailComposeRequest(BaseModel):
    candidate_name: str
    position_title: str
    interview_date: str
    interview_time: str
    duration_minutes: int = 60
    interviewer_names: list[str] = []
    teams_join_url: Optional[str] = None
    company_name: str = "HR Platform"
    extra_notes: str = ""


class EmailSendRequest(EmailComposeRequest):
    to_email: str
    cc_emails: list[str] = []


@router.post("/email/compose")
async def compose_invite_email(
    payload: EmailComposeRequest,
    current_user: dict = Depends(role_required("admin")),
    groq_client: AsyncGroq = Depends(get_openai_client),
):
    agent = EmailInviteAgent(groq_client)
    composed = await agent.compose_email(
        candidate_name=payload.candidate_name,
        position_title=payload.position_title,
        interview_date=payload.interview_date,
        interview_time=payload.interview_time,
        duration_minutes=payload.duration_minutes,
        interviewer_names=payload.interviewer_names,
        teams_join_url=payload.teams_join_url,
        company_name=payload.company_name,
        extra_notes=payload.extra_notes,
    )
    return composed


@router.post("/email/send")
async def send_invite_email(
    payload: EmailSendRequest,
    current_user: dict = Depends(role_required("admin")),
    groq_client: AsyncGroq = Depends(get_openai_client),
):
    agent = EmailInviteAgent(groq_client)
    try:
        result = await agent.compose_and_send(
            to_email=payload.to_email,
            cc_emails=payload.cc_emails,
            candidate_name=payload.candidate_name,
            position_title=payload.position_title,
            interview_date=payload.interview_date,
            interview_time=payload.interview_time,
            duration_minutes=payload.duration_minutes,
            interviewer_names=payload.interviewer_names,
            teams_join_url=payload.teams_join_url,
            company_name=payload.company_name,
            extra_notes=payload.extra_notes,
        )
        return result
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e))


@router.post("/create")
async def create_interview(
    payload: InterviewCreate,
    current_user: dict = Depends(role_required("admin")),
    db: AsyncSession = Depends(get_db),
    openai_client: AsyncGroq = Depends(get_openai_client),
):
    service = InterviewService(db, openai_client)
    return await service.create_interview(
        candidate_id=payload.candidate_id,
        jd_id=payload.jd_id,
        panel_user_id=payload.panel_user_id,
        stage=payload.stage,
        created_by=current_user["sub"],
    )


@router.post("/assign-panel")
async def assign_panel(
    payload: PanelAssignRequest,
    current_user: dict = Depends(role_required("admin")),
    db: AsyncSession = Depends(get_db),
    openai_client: AsyncGroq = Depends(get_openai_client),
):
    service = InterviewService(db, openai_client)
    return await service.assign_panel(
        panel_user_id=payload.panel_user_id,
        candidate_id=payload.candidate_id,
        jd_id=payload.jd_id,
        stage=payload.stage,
        assigned_by=current_user["sub"],
    )


@router.get("/list")
async def list_interviews(
    status: str | None = None,
    jd_id: int | None = None,
    current_user: dict = Depends(role_required("admin")),
    db: AsyncSession = Depends(get_db),
    openai_client: AsyncGroq = Depends(get_openai_client),
):
    service = InterviewService(db, openai_client)
    return await service.get_interviews(status=status, jd_id=jd_id)


@router.get("/assigned")
async def get_assigned_candidates(
    current_user: dict = Depends(role_required("panel")),
    db: AsyncSession = Depends(get_db),
    openai_client: AsyncGroq = Depends(get_openai_client),
):
    service = InterviewService(db, openai_client)
    return await service.get_assigned_candidates(current_user["sub"])


@router.post("/{interview_id}/feedback")
async def submit_feedback(
    interview_id: str,
    payload: FeedbackSubmit,
    current_user: dict = Depends(role_required("panel")),
    db: AsyncSession = Depends(get_db),
    openai_client: AsyncGroq = Depends(get_openai_client),
):
    service = InterviewService(db, openai_client)
    return await service.submit_feedback(
        interview_id=interview_id,
        panel_user_id=current_user["sub"],
        feedback_data=payload.model_dump(),
    )
