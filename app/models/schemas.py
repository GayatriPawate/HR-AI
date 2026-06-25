from pydantic import BaseModel, EmailStr, Field
from typing import Optional, List, Any
from datetime import datetime


# ── Auth ──────────────────────────────────────────────────────
class LoginRequest(BaseModel):
    email: str
    password: str


class LoginResponse(BaseModel):
    token: str
    role: str
    user_id: str
    name: str


class UserCreate(BaseModel):
    email: str
    password: str
    full_name: str
    role: str = "panel"
    department: Optional[str] = None
    ms_email: Optional[str] = None


# ── JD ────────────────────────────────────────────────────────
class JDCreate(BaseModel):
    title: str
    raw_text: str


class JDResponse(BaseModel):
    id: int
    title: str
    mandatory_skills: List[str] = []
    secondary_skills: List[str] = []
    nice_to_have: List[str] = []
    min_experience_yrs: Optional[float] = None
    domain: Optional[str] = None
    status: str
    created_at: Optional[str] = None


# ── Resume ────────────────────────────────────────────────────
class ResumeUploadResult(BaseModel):
    filename: str
    status: str
    candidate_id: Optional[str] = None
    candidate_name: Optional[str] = None
    is_duplicate: bool = False
    skills_found: int = 0
    error: Optional[str] = None


# ── Matching ──────────────────────────────────────────────────
class MatchRequest(BaseModel):
    jd_id: int


class CandidateRankItem(BaseModel):
    candidate_id: str
    full_name: str
    total_score: Optional[float] = None
    tier: Optional[str] = None
    matched_skills: List[str] = []
    missing_skills: List[str] = []
    risk_flags: List[str] = []
    is_shortlisted: bool = False


# ── Status ────────────────────────────────────────────────────
class ShortlistRequest(BaseModel):
    jd_id: int


class StatusUpdate(BaseModel):
    jd_id: int
    status: str
    reason: Optional[str] = ""


# ── Panel Assignment ──────────────────────────────────────────
class PanelAssignRequest(BaseModel):
    candidate_id: str
    jd_id: int
    panel_user_id: str
    stage: str = "technical"


# ── Question Generation ───────────────────────────────────────
class QuestionGenRequest(BaseModel):
    candidate_id: str
    jd_id: int
    categories: Optional[List[str]] = None


# ── Feedback ──────────────────────────────────────────────────
class FeedbackSubmit(BaseModel):
    technical_rating: Optional[int] = Field(None, ge=1, le=5)
    communication_rating: Optional[int] = Field(None, ge=1, le=5)
    problem_solving_rating: Optional[int] = Field(None, ge=1, le=5)
    cultural_fit_rating: Optional[int] = Field(None, ge=1, le=5)
    overall_rating: Optional[int] = Field(None, ge=1, le=5)
    recommendation: Optional[str] = None
    rejection_reason: Optional[str] = None
    strengths: Optional[str] = None
    areas_of_improvement: Optional[str] = None
    comments: Optional[str] = None


# ── Scheduling ────────────────────────────────────────────────
class FindSlotsRequest(BaseModel):
    candidate_id: str
    jd_id: int
    panel_user_emails: List[str]
    date_from: str
    date_to: str
    duration_minutes: int = 60
    timezone: str = "UTC"


class CreateEventRequest(BaseModel):
    candidate_id: str
    jd_id: int
    panel_user_emails: List[str]
    start: str
    end: str
    timezone: str = "UTC"
    create_teams_meeting: bool = True
    subject: Optional[str] = None


class InterviewCreate(BaseModel):
    candidate_id: str
    jd_id: int
    panel_user_id: str
    stage: str = "technical"


# ── Panel Availability & Slot Booking ─────────────────────────

class CandidateChatRequest(BaseModel):
    jd_id: int
    question: str
    top_k: int = 5


class CandidateChatCitation(BaseModel):
    candidate_id: str
    candidate_name: Optional[str]
    excerpt: str
    similarity: float


class CandidateChatResponse(BaseModel):
    answer: str
    citations: List[CandidateChatCitation]


class SlotCreate(BaseModel):
    panel_user_id: str
    jd_id: Optional[int] = None
    slot_start: str   # ISO 8601 e.g. "2026-07-01T10:00:00"
    slot_end: str


class SlotBulkCreate(BaseModel):
    panel_user_id: str
    jd_id: Optional[int] = None
    slots: List[dict]  # list of {"slot_start": ..., "slot_end": ...}


class SlotBookRequest(BaseModel):
    slot_id: str
    candidate_id: str
    jd_id: int
    interview_id: Optional[str] = None
    notes: Optional[str] = None


class SlotResponse(BaseModel):
    id: str
    panel_user_id: str
    panel_name: Optional[str] = None
    jd_id: Optional[int] = None
    slot_start: str
    slot_end: str
    status: str


class BookingResponse(BaseModel):
    id: str
    slot_id: str
    candidate_id: str
    candidate_name: Optional[str] = None
    jd_id: int
    booked_at: str
    notes: Optional[str] = None
