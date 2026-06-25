from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
from typing import Any
from groq import AsyncGroq

from app.db.base import get_db
from app.auth.rbac import role_required
from app.agents.manager_agent import ManagerAgent
from app.utils.openai_client import get_openai_client

router = APIRouter(prefix="/manager", tags=["Manager Agent"])


class ActionRequest(BaseModel):
    action: str
    payload: dict[str, Any] = {}


@router.post("/action")
async def run_action(
    request: ActionRequest,
    current_user: dict = Depends(role_required("admin", "panel")),
    db: AsyncSession = Depends(get_db),
    openai_client: AsyncGroq = Depends(get_openai_client),
):
    """
    Single entry point for all agent-backed actions.
    The ManagerAgent validates role permissions and routes to the
    correct sub-agent or service pipeline.

    Example body:
        { "action": "match_candidates", "payload": { "jd_id": 1 } }
        { "action": "generate_questions", "payload": { "candidate_id": "...", "jd_id": 1 } }
    """
    agent = ManagerAgent(openai_client, db)
    return await agent.handle(
        user_context=current_user,
        action=request.action,
        payload=request.payload,
    )


@router.get("/actions")
async def list_actions(
    current_user: dict = Depends(role_required("admin", "panel")),
):
    """Returns the actions available for the current user's role."""
    role = current_user.get("role", "")

    admin_actions = [
        {"action": "jd_analyzer",           "description": "Analyze a JD and build rubric",         "required_inputs": ["title", "raw_text"]},
        {"action": "match_candidates",       "description": "Run AI matching for all candidates vs JD", "required_inputs": ["jd_id"]},
        {"action": "skill_matcher",          "description": "Get LLM explanation for a candidate-JD match", "required_inputs": ["candidate_id", "jd_id"]},
        {"action": "assign_panel",           "description": "Assign a panel member to a candidate",   "required_inputs": ["candidate_id", "jd_id", "panel_user_id", "stage"]},
        {"action": "update_status",          "description": "Update candidate pipeline status",       "required_inputs": ["candidate_id", "jd_id", "status"]},
        {"action": "get_dashboard_metrics",  "description": "Fetch platform-wide metrics",            "required_inputs": []},
    ]

    panel_actions = [
        {"action": "generate_questions",         "description": "Generate tailored interview questions", "required_inputs": ["candidate_id", "jd_id"]},
        {"action": "feedback_analyzer",          "description": "Analyze submitted interview feedback",  "required_inputs": ["interview_id"]},
        {"action": "get_assigned_candidates",    "description": "List candidates assigned to you",       "required_inputs": []},
        {"action": "get_candidate_score_summary","description": "Get match score breakdown for a candidate", "required_inputs": ["candidate_id", "jd_id"]},
    ]

    if role == "admin":
        return {"role": role, "available_actions": admin_actions}
    return {"role": role, "available_actions": panel_actions}
