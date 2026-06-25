from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from groq import AsyncGroq

from app.db.base import get_db
from app.auth.rbac import role_required
from app.agents.question_generator import QuestionGeneratorAgent
from app.db.models import Candidate, JobDescription, CandidateJobMatch, PanelAssignment
from app.models.schemas import QuestionGenRequest
from app.utils.openai_client import get_openai_client

router = APIRouter(prefix="/questions", tags=["questions"])


@router.post("/generate")
async def generate_questions(
    payload: QuestionGenRequest,
    current_user: dict = Depends(role_required("panel")),  # PANEL ONLY
    db: AsyncSession = Depends(get_db),
    openai_client: AsyncGroq = Depends(get_openai_client),
):
    # Verify panel user is assigned to this candidate
    assignment_result = await db.execute(
        select(PanelAssignment).where(
            and_(
                PanelAssignment.panel_user_id == current_user["sub"],
                PanelAssignment.candidate_id == payload.candidate_id,
                PanelAssignment.jd_id == payload.jd_id,
                PanelAssignment.is_active == True,
            )
        )
    )
    if not assignment_result.scalar_one_or_none():
        raise HTTPException(
            status_code=403,
            detail="You are not assigned to this candidate for this JD",
        )

    # Fetch candidate
    cand_result = await db.execute(
        select(Candidate).where(Candidate.id == payload.candidate_id)
    )
    candidate = cand_result.scalar_one_or_none()
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")

    # Fetch JD
    jd_result = await db.execute(
        select(JobDescription).where(JobDescription.id == payload.jd_id)
    )
    jd = jd_result.scalar_one_or_none()
    if not jd:
        raise HTTPException(status_code=404, detail="JD not found")

    # Fetch score breakdown
    match_result = await db.execute(
        select(CandidateJobMatch).where(
            and_(
                CandidateJobMatch.candidate_id == payload.candidate_id,
                CandidateJobMatch.jd_id == payload.jd_id,
            )
        )
    )
    match = match_result.scalar_one_or_none()
    score_breakdown = match.score_breakdown_json if match else {}

    agent = QuestionGeneratorAgent(openai_client)
    questions = await agent.generate(
        candidate_profile={
            "full_name": candidate.full_name,
            "skills_list": candidate.skills_list or [],
            "total_experience_yrs": candidate.total_experience_yrs,
            "latest_role": candidate.latest_role,
            "domain_text": candidate.domain_text,
        },
        jd_data={
            "title": jd.title,
            "mandatory_skills": jd.mandatory_skills or [],
            "secondary_skills": jd.secondary_skills or [],
            "domain": jd.domain,
            "soft_skills": jd.soft_skills or [],
        },
        score_breakdown=score_breakdown,
        categories=payload.categories,
    )

    return {
        "candidate_id": payload.candidate_id,
        "candidate_name": candidate.full_name,
        "jd_id": payload.jd_id,
        "jd_title": jd.title,
        "questions": questions,
        "total": len(questions),
    }
