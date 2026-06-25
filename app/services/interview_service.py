import uuid
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from groq import AsyncGroq
from datetime import datetime

from app.db.models import (
    Interview, InterviewFeedback, PanelAssignment,
    CandidateStatus, Candidate, JobDescription, User
)
from app.agents.feedback_analyzer import FeedbackAnalyzerAgent


class InterviewService:
    def __init__(self, db: AsyncSession, openai_client: AsyncGroq):
        self.db = db
        self.openai = openai_client
        self.feedback_analyzer = FeedbackAnalyzerAgent(openai_client)

    async def create_interview(
        self,
        candidate_id: str,
        jd_id: int,
        panel_user_id: str,
        stage: str,
        created_by: str,
    ) -> dict:
        interview = Interview(
            id=str(uuid.uuid4()),
            candidate_id=candidate_id,
            jd_id=jd_id,
            panel_user_id=panel_user_id,
            stage=stage,
            status="pending",
            created_by=created_by,
        )
        self.db.add(interview)

        # Update candidate status
        await self._upsert_status(candidate_id, jd_id, "Interview Pending")
        await self.db.commit()
        return {"interview_id": interview.id, "status": "pending"}

    async def assign_panel(
        self,
        panel_user_id: str,
        candidate_id: str,
        jd_id: int,
        stage: str,
        assigned_by: str,
    ) -> dict:
        assignment = PanelAssignment(
            panel_user_id=panel_user_id,
            candidate_id=candidate_id,
            jd_id=jd_id,
            interview_stage=stage,
            assigned_by=assigned_by,
        )
        self.db.add(assignment)
        await self.db.commit()
        return {"assignment_id": assignment.id}

    async def get_assigned_candidates(self, panel_user_id: str) -> list[dict]:
        result = await self.db.execute(
            select(PanelAssignment, Candidate, JobDescription)
            .join(Candidate, PanelAssignment.candidate_id == Candidate.id)
            .join(JobDescription, PanelAssignment.jd_id == JobDescription.id)
            .where(
                and_(
                    PanelAssignment.panel_user_id == panel_user_id,
                    PanelAssignment.is_active == True,
                )
            )
        )
        rows = result.all()
        return [
            {
                "assignment_id": row[0].id,
                "candidate_id": row[1].id,
                "candidate_name": row[1].full_name,
                "candidate_email": row[1].email,
                "latest_role": row[1].latest_role,
                "total_experience_yrs": row[1].total_experience_yrs,
                "jd_id": row[2].id,
                "jd_title": row[2].title,
                "stage": row[0].interview_stage,
                "assigned_at": row[0].assigned_at.isoformat() if row[0].assigned_at else None,
            }
            for row in rows
        ]

    async def submit_feedback(
        self,
        interview_id: str,
        panel_user_id: str,
        feedback_data: dict,
    ) -> dict:
        # Verify panel user owns this interview
        int_result = await self.db.execute(
            select(Interview).where(Interview.id == interview_id)
        )
        interview = int_result.scalar_one_or_none()
        if not interview:
            raise ValueError("Interview not found")

        # Analyze feedback with LLM
        llm_analysis = await self.feedback_analyzer.analyze(feedback_data)

        feedback = InterviewFeedback(
            id=str(uuid.uuid4()),
            interview_id=interview_id,
            candidate_id=interview.candidate_id,
            panel_user_id=panel_user_id,
            technical_rating=feedback_data.get("technical_rating"),
            communication_rating=feedback_data.get("communication_rating"),
            problem_solving_rating=feedback_data.get("problem_solving_rating"),
            cultural_fit_rating=feedback_data.get("cultural_fit_rating"),
            overall_rating=feedback_data.get("overall_rating"),
            recommendation=feedback_data.get("recommendation"),
            rejection_reason=feedback_data.get("rejection_reason"),
            strengths=feedback_data.get("strengths"),
            areas_of_improvement=feedback_data.get("areas_of_improvement"),
            comments=feedback_data.get("comments"),
            llm_analysis=llm_analysis,
        )
        self.db.add(feedback)

        # Update interview status
        interview.status = "completed"
        interview.completed_at = datetime.utcnow()

        # Update candidate status
        recommendation = feedback_data.get("recommendation", "")
        if "Do Not Recommend" in recommendation:
            new_status = "Rejected"
        elif "Strongly Recommend" in recommendation or "Recommend" in recommendation:
            new_status = "Interview Completed"
        else:
            new_status = "Interview Completed"

        await self._upsert_status(interview.candidate_id, interview.jd_id, new_status)
        await self.db.commit()

        return {"feedback_id": feedback.id, "status": "submitted", "llm_signal": llm_analysis.get("overall_signal")}

    async def get_interviews(
        self,
        status: str | None = None,
        jd_id: int | None = None,
    ) -> list[dict]:
        query = select(Interview)
        if status:
            query = query.where(Interview.status == status)
        if jd_id:
            query = query.where(Interview.jd_id == jd_id)
        query = query.order_by(Interview.created_at.desc())
        result = await self.db.execute(query)
        return [
            {
                "id": i.id,
                "candidate_id": i.candidate_id,
                "jd_id": i.jd_id,
                "panel_user_id": i.panel_user_id,
                "stage": i.stage,
                "status": i.status,
                "scheduled_at": i.scheduled_at.isoformat() if i.scheduled_at else None,
                "completed_at": i.completed_at.isoformat() if i.completed_at else None,
            }
            for i in result.scalars().all()
        ]

    async def _upsert_status(self, candidate_id: str, jd_id: int, status: str):
        result = await self.db.execute(
            select(CandidateStatus).where(
                and_(
                    CandidateStatus.candidate_id == candidate_id,
                    CandidateStatus.jd_id == jd_id,
                )
            )
        )
        rec = result.scalar_one_or_none()
        if rec:
            rec.status = status
        else:
            self.db.add(CandidateStatus(candidate_id=candidate_id, jd_id=jd_id, status=status))
