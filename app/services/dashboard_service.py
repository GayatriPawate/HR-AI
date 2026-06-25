from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, text
from app.db.models import (
    Candidate, CandidateJobMatch, CandidateStatus,
    Interview, InterviewSchedule, InterviewFeedback,
    JobDescription, StatusHistory
)


class DashboardService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_metrics(self, jd_id: int | None = None) -> dict:
        total_q = select(func.count(Candidate.id))
        result = await self.db.execute(total_q)
        total = result.scalar() or 0

        # Status counts
        status_counts = {}
        for status in ["New", "Screened", "Shortlisted", "Interview Pending",
                        "Interview Scheduled", "Interview Completed", "Rejected", "Selected", "On Hold"]:
            q = select(func.count(CandidateStatus.id)).where(CandidateStatus.status == status)
            if jd_id:
                q = q.where(CandidateStatus.jd_id == jd_id)
            r = await self.db.execute(q)
            status_counts[status] = r.scalar() or 0

        # Average scores per JD
        avg_score_q = (
            select(CandidateJobMatch.jd_id, func.avg(CandidateJobMatch.total_score))
            .group_by(CandidateJobMatch.jd_id)
        )
        if jd_id:
            avg_score_q = avg_score_q.where(CandidateJobMatch.jd_id == jd_id)
        avg_result = await self.db.execute(avg_score_q)
        avg_scores = [{"jd_id": r[0], "avg_score": round(r[1] or 0, 2)} for r in avg_result.all()]

        # Tier distribution
        tier_q = (
            select(CandidateJobMatch.tier, func.count(CandidateJobMatch.id))
            .group_by(CandidateJobMatch.tier)
        )
        if jd_id:
            tier_q = tier_q.where(CandidateJobMatch.jd_id == jd_id)
        tier_result = await self.db.execute(tier_q)
        tier_dist = [{"tier": r[0], "count": r[1]} for r in tier_result.all()]

        # Upcoming schedules
        sched_q = (
            select(InterviewSchedule)
            .where(InterviewSchedule.status == "scheduled")
            .order_by(InterviewSchedule.scheduled_start)
            .limit(10)
        )
        sched_result = await self.db.execute(sched_q)
        upcoming = []
        for s in sched_result.scalars().all():
            upcoming.append({
                "schedule_id": s.id,
                "candidate_id": s.candidate_id,
                "jd_id": s.jd_id,
                "scheduled_start": s.scheduled_start.isoformat() if s.scheduled_start else None,
                "scheduled_end": s.scheduled_end.isoformat() if s.scheduled_end else None,
                "teams_join_url": s.teams_join_url,
                "status": s.status,
            })

        return {
            "total_candidates": total,
            "status_breakdown": status_counts,
            "shortlisted": status_counts.get("Shortlisted", 0),
            "interview_pending": status_counts.get("Interview Pending", 0),
            "interview_scheduled": status_counts.get("Interview Scheduled", 0),
            "interview_completed": status_counts.get("Interview Completed", 0),
            "rejected": status_counts.get("Rejected", 0),
            "selected": status_counts.get("Selected", 0),
            "avg_scores_by_jd": avg_scores,
            "tier_distribution": tier_dist,
            "upcoming_schedules": upcoming,
            "funnel": [
                {"stage": s, "count": status_counts.get(s, 0)}
                for s in ["New", "Screened", "Shortlisted", "Interview Pending",
                          "Interview Scheduled", "Interview Completed", "Selected", "Rejected"]
            ],
        }

    async def get_candidate_detail(self, candidate_id: str, jd_id: int | None = None) -> dict | None:
        result = await self.db.execute(
            select(Candidate).where(Candidate.id == candidate_id)
        )
        candidate = result.scalar_one_or_none()
        if not candidate:
            return None

        detail = {
            "id": candidate.id,
            "full_name": candidate.full_name,
            "email": candidate.email,
            "phone": candidate.phone,
            "location": candidate.location,
            "total_experience_yrs": candidate.total_experience_yrs,
            "latest_role": candidate.latest_role,
            "current_company": candidate.current_company,
            "skills_list": candidate.skills_list or [],
            "education": candidate.education or [],
            "certifications": candidate.certifications or [],
            "domain_text": candidate.domain_text,
        }

        # Get match data
        if jd_id:
            m_result = await self.db.execute(
                select(CandidateJobMatch).where(
                    CandidateJobMatch.candidate_id == candidate_id,
                    CandidateJobMatch.jd_id == jd_id,
                )
            )
            match = m_result.scalar_one_or_none()
            if match:
                detail["match"] = {
                    "total_score": match.total_score,
                    "tier": match.tier,
                    "matched_skills": match.matched_skills or [],
                    "missing_skills": match.missing_skills or [],
                    "risk_flags": match.risk_flags or [],
                    "match_explanation": match.match_explanation,
                    "score_breakdown": match.score_breakdown_json,
                    "is_shortlisted": match.is_shortlisted,
                }

        # Status history
        sh_result = await self.db.execute(
            select(StatusHistory)
            .where(StatusHistory.candidate_id == candidate_id)
            .order_by(StatusHistory.changed_at.desc())
            .limit(20)
        )
        detail["status_history"] = [
            {
                "from_status": h.from_status,
                "to_status": h.to_status,
                "reason": h.reason,
                "changed_at": h.changed_at.isoformat() if h.changed_at else None,
            }
            for h in sh_result.scalars().all()
        ]

        # Interview history
        int_result = await self.db.execute(
            select(Interview, InterviewFeedback)
            .outerjoin(InterviewFeedback, Interview.id == InterviewFeedback.interview_id)
            .where(Interview.candidate_id == candidate_id)
            .order_by(Interview.created_at.desc())
        )
        interviews = []
        seen = set()
        for row in int_result.all():
            interview, feedback = row
            if interview.id not in seen:
                seen.add(interview.id)
                interviews.append({
                    "interview_id": interview.id,
                    "stage": interview.stage,
                    "status": interview.status,
                    "scheduled_at": interview.scheduled_at.isoformat() if interview.scheduled_at else None,
                    "feedback": {
                        "overall_rating": feedback.overall_rating,
                        "recommendation": feedback.recommendation,
                        "strengths": feedback.strengths,
                        "rejection_reason": feedback.rejection_reason,
                    } if feedback else None,
                })
        detail["interviews"] = interviews

        return detail

    async def update_candidate_status(
        self,
        candidate_id: str,
        jd_id: int,
        new_status: str,
        changed_by: str,
        reason: str = "",
    ) -> bool:
        from app.db.models import StatusHistory
        result = await self.db.execute(
            select(CandidateStatus).where(
                CandidateStatus.candidate_id == candidate_id,
                CandidateStatus.jd_id == jd_id,
            )
        )
        status_rec = result.scalar_one_or_none()
        old_status = status_rec.status if status_rec else None

        if status_rec:
            status_rec.status = new_status
        else:
            self.db.add(CandidateStatus(
                candidate_id=candidate_id, jd_id=jd_id, status=new_status
            ))

        self.db.add(StatusHistory(
            candidate_id=candidate_id,
            jd_id=jd_id,
            from_status=old_status,
            to_status=new_status,
            reason=reason,
            changed_by=changed_by,
        ))
        await self.db.commit()
        return True
