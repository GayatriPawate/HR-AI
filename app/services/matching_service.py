from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from groq import AsyncGroq
from datetime import datetime

from app.db.models import Candidate, JobDescription, CandidateJobMatch, CandidateStatus, Resume
from app.services.scoring_service import ScoringService
from app.agents.skill_matcher import SkillMatcherAgent


class MatchingService:
    def __init__(self, db: AsyncSession, openai_client: AsyncGroq):
        self.db = db
        self.openai = openai_client
        self.scorer = ScoringService(openai_client)
        self.explainer = SkillMatcherAgent(openai_client)

    async def match_all_candidates_for_jd(self, jd_id: int) -> list[dict]:
        jd_result = await self.db.execute(
            select(JobDescription).where(JobDescription.id == jd_id)
        )
        jd = jd_result.scalar_one_or_none()
        if not jd:
            raise ValueError(f"JD {jd_id} not found")

        jd_dict = {
            "id": jd.id,
            "title": jd.title,
            "mandatory_skills": jd.mandatory_skills or [],
            "secondary_skills": jd.secondary_skills or [],
            "nice_to_have": jd.nice_to_have or [],
            "min_experience_yrs": jd.min_experience_yrs or 0,
            "domain": jd.domain or "",
            "synonym_map": jd.synonym_map or {},
            "education_requirements": jd.education_requirements or {},
            "rubric": jd.rubric,
        }

        candidates_result = await self.db.execute(select(Candidate))
        candidates = candidates_result.scalars().all()

        results = []
        for candidate in candidates:
            try:
                result = await self._score_one(candidate, jd_dict)
                results.append(result)
            except Exception as e:
                results.append({
                    "candidate_id": candidate.id,
                    "candidate_name": candidate.full_name,
                    "error": str(e),
                    "total_score": 0,
                    "tier": "Not Suitable",
                })

        return sorted(results, key=lambda x: -(x.get("total_score") or 0))

    async def _score_one(self, candidate: Candidate, jd_dict: dict) -> dict:
        cand_dict = {
            "id": candidate.id,
            "full_name": candidate.full_name,
            "skills_list": candidate.skills_list or [],
            "total_experience_yrs": candidate.total_experience_yrs or 0,
            "domain_text": candidate.domain_text or "",
            "education": candidate.education or [],
            "certifications": candidate.certifications or [],
            "latest_role": candidate.latest_role,
        }

        score_data = await self.scorer.score_candidate(cand_dict, jd_dict)

        # Get LLM explanation
        explanation_data = await self.explainer.explain_match(
            candidate_profile=cand_dict,
            jd_rubric=jd_dict.get("rubric") or {},
            computed_scores=score_data["score_breakdown"],
        )

        # Upsert into DB
        existing_result = await self.db.execute(
            select(CandidateJobMatch).where(
                CandidateJobMatch.candidate_id == candidate.id,
                CandidateJobMatch.jd_id == jd_dict["id"],
            )
        )
        existing = existing_result.scalar_one_or_none()
        bd = score_data["score_breakdown"]

        if existing:
            existing.mandatory_score   = bd["mandatory_skills"]["raw"]
            existing.secondary_score   = bd["secondary_skills"]["raw"]
            existing.experience_score  = bd["experience"]["raw"]
            existing.domain_score      = bd["domain"]["raw"]
            existing.education_score   = bd["education"]["raw"]
            existing.semantic_score    = bd["semantic"]["raw"]
            existing.total_score       = score_data["total_score"]
            existing.tier              = score_data["tier"]
            existing.matched_skills    = score_data["matched_skills"]
            existing.missing_skills    = score_data["missing_skills"]
            existing.risk_flags        = score_data["risk_flags"]
            existing.match_explanation = explanation_data.get("match_explanation", "")
            existing.score_breakdown_json = bd
        else:
            match = CandidateJobMatch(
                candidate_id=candidate.id,
                jd_id=jd_dict["id"],
                mandatory_score   = bd["mandatory_skills"]["raw"],
                secondary_score   = bd["secondary_skills"]["raw"],
                experience_score  = bd["experience"]["raw"],
                domain_score      = bd["domain"]["raw"],
                education_score   = bd["education"]["raw"],
                semantic_score    = bd["semantic"]["raw"],
                total_score       = score_data["total_score"],
                tier              = score_data["tier"],
                matched_skills    = score_data["matched_skills"],
                missing_skills    = score_data["missing_skills"],
                risk_flags        = score_data["risk_flags"],
                match_explanation = explanation_data.get("match_explanation", ""),
                score_breakdown_json = bd,
            )
            self.db.add(match)

            # Upsert status
            status_result = await self.db.execute(
                select(CandidateStatus).where(
                    CandidateStatus.candidate_id == candidate.id,
                    CandidateStatus.jd_id == jd_dict["id"],
                )
            )
            if not status_result.scalar_one_or_none():
                self.db.add(CandidateStatus(
                    candidate_id=candidate.id,
                    jd_id=jd_dict["id"],
                    status="Screened",
                ))

        await self.db.commit()

        return {
            "candidate_id": candidate.id,
            "candidate_name": candidate.full_name,
            "email": candidate.email,
            "latest_role": candidate.latest_role,
            "total_experience_yrs": candidate.total_experience_yrs,
            **score_data,
            "match_explanation": explanation_data.get("match_explanation", ""),
            "recommendation_note": explanation_data.get("recommendation_note", ""),
        }

    async def get_ranked_candidates(
        self,
        jd_id: int,
        tier: str | None = None,
        min_score: float = 0,
        limit: int = 50,
        offset: int = 0,
    ) -> list[dict]:
        from sqlalchemy import desc
        query = (
            select(Candidate, CandidateJobMatch)
            .join(CandidateJobMatch, Candidate.id == CandidateJobMatch.candidate_id)
            .where(CandidateJobMatch.jd_id == jd_id)
            .where(CandidateJobMatch.total_score >= min_score)
        )
        if tier:
            query = query.where(CandidateJobMatch.tier == tier)
        query = query.order_by(desc(CandidateJobMatch.total_score)).limit(limit).offset(offset)

        results = await self.db.execute(query)
        rows = results.all()
        return [
            {
                "candidate_id": row[0].id,
                "serial_no": f"C{str(row[0].serial_no).zfill(3)}" if row[0].serial_no else "—",
                "full_name": row[0].full_name,
                "email": row[0].email,
                "latest_role": row[0].latest_role,
                "total_experience_yrs": row[0].total_experience_yrs,
                "location": row[0].location,
                "total_score": row[1].total_score,
                "tier": row[1].tier,
                "matched_skills": row[1].matched_skills or [],
                "missing_skills": row[1].missing_skills or [],
                "risk_flags": row[1].risk_flags or [],
                "is_shortlisted": row[1].is_shortlisted,
                "match_explanation": row[1].match_explanation,
                "score_breakdown": row[1].score_breakdown_json,
            }
            for row in rows
        ]

    async def shortlist_candidate(
        self,
        candidate_id: str,
        jd_id: int,
        shortlisted_by: str,
    ) -> bool:
        result = await self.db.execute(
            select(CandidateJobMatch).where(
                CandidateJobMatch.candidate_id == candidate_id,
                CandidateJobMatch.jd_id == jd_id,
            )
        )
        match = result.scalar_one_or_none()
        if not match:
            return False

        match.is_shortlisted = True
        match.shortlisted_by = shortlisted_by
        match.shortlisted_at = datetime.utcnow()

        # Update status
        status_result = await self.db.execute(
            select(CandidateStatus).where(
                CandidateStatus.candidate_id == candidate_id,
                CandidateStatus.jd_id == jd_id,
            )
        )
        status = status_result.scalar_one_or_none()
        if status:
            status.status = "Shortlisted"
        else:
            self.db.add(CandidateStatus(
                candidate_id=candidate_id, jd_id=jd_id, status="Shortlisted"
            ))

        await self.db.commit()
        return True
