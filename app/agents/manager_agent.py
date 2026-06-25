import json
from groq import AsyncGroq
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_

from app.prompts.prompts import MANAGER_AGENT_SYSTEM_PROMPT
from app.agents.jd_analyzer import JDAnalyzerAgent
from app.agents.rubric_agent import RubricAgent
from app.agents.skill_matcher import SkillMatcherAgent
from app.agents.question_generator import QuestionGeneratorAgent
from app.agents.feedback_analyzer import FeedbackAnalyzerAgent
from app.services.jd_service import JDService
from app.services.matching_service import MatchingService
from app.db.models import (
    Candidate, JobDescription, CandidateJobMatch,
    Interview, InterviewFeedback, PanelAssignment,
    CandidateStatus, StatusHistory,
)
from config.settings import get_settings

settings = get_settings()


class ManagerAgent:
    """
    Orchestration agent that routes action requests to the correct
    sub-agent or service pipeline based on user role.

    Flow:
        1. LLM routing call  → decides which agent + validates inputs
        2. ACCESS_DENIED / MISSING_INPUTS guard
        3. Dispatch to the matching pipeline
        4. Return unified { action, agent_used, result, priority }
    """

    def __init__(self, client: AsyncGroq, db: AsyncSession):
        self.client = client
        self.db = db
        # Sub-agents (shared client)
        self.jd_analyzer = JDAnalyzerAgent(client)
        self.rubric_agent = RubricAgent(client)
        self.skill_matcher = SkillMatcherAgent(client)
        self.question_generator = QuestionGeneratorAgent(client)
        self.feedback_analyzer = FeedbackAnalyzerAgent(client)

    # ── Public entry point ────────────────────────────────────────

    async def handle(self, user_context: dict, action: str, payload: dict) -> dict:
        """
        user_context: {"sub": str, "role": "admin"|"panel", "name": str}
        action:       e.g. "match_candidates", "generate_questions"
        payload:      action-specific parameters
        """
        role = user_context.get("role", "")

        # Step 1: Ask LLM to validate + route
        routing = await self._route(role, action, payload)

        # Step 2: Handle error responses from LLM
        if "error" in routing:
            return {
                "action": action,
                "agent_used": None,
                "result": routing,
                "priority": None,
            }

        agent_name = routing["agent"]
        inputs = routing.get("inputs", {})
        priority = routing.get("priority", "medium")

        # Step 3: Execute the pipeline
        result = await self._dispatch(agent_name, inputs, user_context)

        return {
            "action": action,
            "agent_used": agent_name,
            "result": result,
            "priority": priority,
        }

    # ── LLM routing call ─────────────────────────────────────────

    async def _route(self, role: str, action: str, payload: dict) -> dict:
        user_message = json.dumps({
            "role": role,
            "action": action,
            "payload": payload,
        })

        for attempt in range(2):
            try:
                response = await self.client.chat.completions.create(
                    model=settings.groq_model,
                    messages=[
                        {"role": "system", "content": MANAGER_AGENT_SYSTEM_PROMPT},
                        {"role": "user", "content": user_message},
                    ],
                    response_format={"type": "json_object"},
                    temperature=0.0,
                )
                return json.loads(response.choices[0].message.content)
            except Exception:
                if attempt == 1:
                    return {"error": "ROUTING_FAILED", "action": action, "role": role}
        return {}

    # ── Pipeline dispatcher ───────────────────────────────────────

    async def _dispatch(self, agent_name: str, inputs: dict, user_context: dict) -> dict:
        dispatch_map = {
            "jd_analyzer":                self._run_jd_analyzer,
            "skill_matcher":              self._run_skill_matcher,
            "question_generator":         self._run_question_generator,
            "feedback_analyzer":          self._run_feedback_analyzer,
            "match_candidates":           self._run_match_candidates,
            "assign_panel":               self._run_assign_panel,
            "update_status":              self._run_update_status,
            "get_dashboard_metrics":      self._run_get_dashboard_metrics,
            "get_assigned_candidates":    self._run_get_assigned_candidates,
            "get_candidate_score_summary": self._run_get_candidate_score_summary,
        }

        handler = dispatch_map.get(agent_name)
        if not handler:
            return {"error": "UNKNOWN_AGENT", "agent": agent_name}

        try:
            return await handler(inputs, user_context)
        except Exception as e:
            return {"error": "PIPELINE_ERROR", "agent": agent_name, "detail": str(e)}

    # ── Individual pipeline handlers ──────────────────────────────

    async def _run_jd_analyzer(self, inputs: dict, user_context: dict) -> dict:
        svc = JDService(self.db, self.client)
        return await svc.create_and_analyze(
            title=inputs["title"],
            raw_text=inputs["raw_text"],
            created_by=user_context["sub"],
        )

    async def _run_skill_matcher(self, inputs: dict, _: dict) -> dict:
        candidate_id = inputs["candidate_id"]
        jd_id = int(inputs["jd_id"])

        cand_result = await self.db.execute(
            select(Candidate).where(Candidate.id == candidate_id)
        )
        candidate = cand_result.scalar_one_or_none()
        if not candidate:
            return {"error": "CANDIDATE_NOT_FOUND", "candidate_id": candidate_id}

        jd_result = await self.db.execute(
            select(JobDescription).where(JobDescription.id == jd_id)
        )
        jd = jd_result.scalar_one_or_none()
        if not jd:
            return {"error": "JD_NOT_FOUND", "jd_id": jd_id}

        match_result = await self.db.execute(
            select(CandidateJobMatch).where(
                and_(
                    CandidateJobMatch.candidate_id == candidate_id,
                    CandidateJobMatch.jd_id == jd_id,
                )
            )
        )
        match = match_result.scalar_one_or_none()
        score_breakdown = match.score_breakdown_json if match else {}

        explanation = await self.skill_matcher.explain_match(
            candidate_profile={
                "full_name": candidate.full_name,
                "skills_list": candidate.skills_list or [],
                "total_experience_yrs": candidate.total_experience_yrs,
                "latest_role": candidate.latest_role,
                "domain_text": candidate.domain_text,
            },
            jd_rubric=jd.rubric or {},
            computed_scores=score_breakdown,
        )
        return {
            "candidate_id": candidate_id,
            "candidate_name": candidate.full_name,
            "jd_id": jd_id,
            **explanation,
        }

    async def _run_question_generator(self, inputs: dict, user_context: dict) -> dict:
        candidate_id = inputs["candidate_id"]
        jd_id = int(inputs["jd_id"])
        categories = inputs.get("categories")

        cand_result = await self.db.execute(
            select(Candidate).where(Candidate.id == candidate_id)
        )
        candidate = cand_result.scalar_one_or_none()
        if not candidate:
            return {"error": "CANDIDATE_NOT_FOUND", "candidate_id": candidate_id}

        jd_result = await self.db.execute(
            select(JobDescription).where(JobDescription.id == jd_id)
        )
        jd = jd_result.scalar_one_or_none()
        if not jd:
            return {"error": "JD_NOT_FOUND", "jd_id": jd_id}

        match_result = await self.db.execute(
            select(CandidateJobMatch).where(
                and_(
                    CandidateJobMatch.candidate_id == candidate_id,
                    CandidateJobMatch.jd_id == jd_id,
                )
            )
        )
        match = match_result.scalar_one_or_none()
        score_breakdown = match.score_breakdown_json if match else {}

        questions = await self.question_generator.generate(
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
            categories=categories,
        )
        return {
            "candidate_id": candidate_id,
            "candidate_name": candidate.full_name,
            "jd_id": jd_id,
            "jd_title": jd.title,
            "questions": questions,
            "total": len(questions),
        }

    async def _run_feedback_analyzer(self, inputs: dict, _: dict) -> dict:
        interview_id = inputs["interview_id"]

        iv_result = await self.db.execute(
            select(Interview).where(Interview.id == interview_id)
        )
        interview = iv_result.scalar_one_or_none()
        if not interview:
            return {"error": "INTERVIEW_NOT_FOUND", "interview_id": interview_id}

        fb_result = await self.db.execute(
            select(InterviewFeedback).where(
                InterviewFeedback.interview_id == interview_id
            )
        )
        feedback_obj = fb_result.scalar_one_or_none()
        if not feedback_obj:
            return {"error": "FEEDBACK_NOT_FOUND", "interview_id": interview_id}

        feedback_dict = {
            "technical_rating": feedback_obj.technical_rating,
            "communication_rating": feedback_obj.communication_rating,
            "problem_solving_rating": feedback_obj.problem_solving_rating,
            "cultural_fit_rating": feedback_obj.cultural_fit_rating,
            "overall_rating": feedback_obj.overall_rating,
            "recommendation": feedback_obj.recommendation,
            "rejection_reason": feedback_obj.rejection_reason,
            "strengths": feedback_obj.strengths,
            "areas_of_improvement": feedback_obj.areas_of_improvement,
            "comments": feedback_obj.comments,
        }

        analysis = await self.feedback_analyzer.analyze(feedback_dict)
        return {
            "interview_id": interview_id,
            "candidate_id": str(interview.candidate_id),
            **analysis,
        }

    async def _run_match_candidates(self, inputs: dict, _: dict) -> dict:
        svc = MatchingService(self.db, self.client)
        results = await svc.match_all_candidates_for_jd(int(inputs["jd_id"]))
        return {"jd_id": inputs["jd_id"], "total_matched": len(results), "results": results}

    async def _run_assign_panel(self, inputs: dict, user_context: dict) -> dict:
        assignment = PanelAssignment(
            panel_user_id=inputs["panel_user_id"],
            candidate_id=inputs["candidate_id"],
            jd_id=int(inputs["jd_id"]),
            interview_stage=inputs.get("stage", "screening"),
            assigned_by=user_context["sub"],
            is_active=True,
        )
        self.db.add(assignment)
        await self.db.commit()
        await self.db.refresh(assignment)
        return {
            "assignment_id": assignment.id,
            "candidate_id": inputs["candidate_id"],
            "panel_user_id": inputs["panel_user_id"],
            "stage": inputs.get("stage", "screening"),
        }

    async def _run_update_status(self, inputs: dict, user_context: dict) -> dict:
        candidate_id = inputs["candidate_id"]
        jd_id = int(inputs["jd_id"])
        new_status = inputs["status"]
        reason = inputs.get("reason", "")

        result = await self.db.execute(
            select(CandidateStatus).where(
                and_(
                    CandidateStatus.candidate_id == candidate_id,
                    CandidateStatus.jd_id == jd_id,
                )
            )
        )
        status_obj = result.scalar_one_or_none()
        old_status = status_obj.status if status_obj else "Unknown"

        if status_obj:
            status_obj.status = new_status
        else:
            self.db.add(CandidateStatus(
                candidate_id=candidate_id,
                jd_id=jd_id,
                status=new_status,
            ))

        self.db.add(StatusHistory(
            candidate_id=candidate_id,
            jd_id=jd_id,
            from_status=old_status,
            to_status=new_status,
            reason=reason,
            changed_by=user_context["sub"],
        ))
        await self.db.commit()
        return {
            "candidate_id": candidate_id,
            "jd_id": jd_id,
            "old_status": old_status,
            "new_status": new_status,
        }

    async def _run_get_dashboard_metrics(self, _: dict, __: dict) -> dict:
        from sqlalchemy import func
        from app.db.models import Resume

        total_candidates = (await self.db.execute(
            select(func.count()).select_from(Candidate)
        )).scalar_one()
        total_jds = (await self.db.execute(
            select(func.count()).select_from(JobDescription)
        )).scalar_one()
        total_interviews = (await self.db.execute(
            select(func.count()).select_from(Interview)
        )).scalar_one()
        total_resumes = (await self.db.execute(
            select(func.count()).select_from(Resume)
        )).scalar_one()

        return {
            "total_candidates": total_candidates,
            "total_jds": total_jds,
            "total_interviews": total_interviews,
            "total_resumes": total_resumes,
        }

    async def _run_get_assigned_candidates(self, _: dict, user_context: dict) -> dict:
        result = await self.db.execute(
            select(PanelAssignment).where(
                and_(
                    PanelAssignment.panel_user_id == user_context["sub"],
                    PanelAssignment.is_active == True,
                )
            )
        )
        assignments = result.scalars().all()
        return {
            "assignments": [
                {
                    "candidate_id": str(a.candidate_id),
                    "jd_id": a.jd_id,
                    "stage": a.interview_stage,
                }
                for a in assignments
            ],
            "total": len(assignments),
        }

    async def _run_get_candidate_score_summary(self, inputs: dict, _: dict) -> dict:
        candidate_id = inputs["candidate_id"]
        jd_id = int(inputs["jd_id"])

        result = await self.db.execute(
            select(CandidateJobMatch).where(
                and_(
                    CandidateJobMatch.candidate_id == candidate_id,
                    CandidateJobMatch.jd_id == jd_id,
                )
            )
        )
        match = result.scalar_one_or_none()
        if not match:
            return {"error": "MATCH_NOT_FOUND", "candidate_id": candidate_id, "jd_id": jd_id}

        return {
            "candidate_id": candidate_id,
            "jd_id": jd_id,
            "total_score": match.total_score,
            "tier": match.tier,
            "mandatory_score": match.mandatory_score,
            "secondary_score": match.secondary_score,
            "experience_score": match.experience_score,
            "domain_score": match.domain_score,
            "education_score": match.education_score,
            "semantic_score": match.semantic_score,
            "matched_skills": match.matched_skills or [],
            "missing_skills": match.missing_skills or [],
            "match_explanation": match.match_explanation or "",
        }
