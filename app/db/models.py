import uuid
from datetime import datetime
from typing import Optional
from sqlalchemy import (
    String, Text, Integer, Float, Boolean, DateTime, ForeignKey,
    UniqueConstraint, CheckConstraint, BigInteger
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.sqlite import JSON
from app.db.base import Base


def new_uuid() -> str:
    return str(uuid.uuid4())


def now() -> datetime:
    return datetime.utcnow()


# ──────────────────────────────────────────────────────────────
# USERS & RBAC
# ──────────────────────────────────────────────────────────────

class Role(Base):
    __tablename__ = "roles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)


class Permission(Base):
    __tablename__ = "permissions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)


class RolePermission(Base):
    __tablename__ = "role_permissions"

    role_id: Mapped[int] = mapped_column(Integer, ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True)
    permission_id: Mapped[int] = mapped_column(Integer, ForeignKey("permissions.id", ondelete="CASCADE"), primary_key=True)


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    department: Mapped[Optional[str]] = mapped_column(String(100))
    ms_email: Mapped[Optional[str]] = mapped_column(String(255))  # MS Graph email
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=now, onupdate=now)

    user_roles: Mapped[list["UserRole"]] = relationship("UserRole", back_populates="user", foreign_keys="[UserRole.user_id]")


class UserRole(Base):
    __tablename__ = "user_roles"

    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    role_id: Mapped[int] = mapped_column(Integer, ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True)
    assigned_by: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("users.id"))
    assigned_at: Mapped[datetime] = mapped_column(DateTime, default=now)

    user: Mapped["User"] = relationship("User", back_populates="user_roles", foreign_keys=[user_id])
    role: Mapped["Role"] = relationship("Role")


# ──────────────────────────────────────────────────────────────
# JOB DESCRIPTIONS
# ──────────────────────────────────────────────────────────────

class JobDescription(Base):
    __tablename__ = "job_descriptions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    raw_text: Mapped[str] = mapped_column(Text, nullable=False)
    mandatory_skills: Mapped[Optional[dict]] = mapped_column(JSON)
    secondary_skills: Mapped[Optional[dict]] = mapped_column(JSON)
    nice_to_have: Mapped[Optional[dict]] = mapped_column(JSON)
    min_experience_yrs: Mapped[Optional[float]] = mapped_column(Float)
    max_experience_yrs: Mapped[Optional[float]] = mapped_column(Float)
    domain: Mapped[Optional[str]] = mapped_column(String(100))
    industry: Mapped[Optional[str]] = mapped_column(String(100))
    soft_skills: Mapped[Optional[dict]] = mapped_column(JSON)
    synonym_map: Mapped[Optional[dict]] = mapped_column(JSON)
    rubric: Mapped[Optional[dict]] = mapped_column(JSON)
    education_requirements: Mapped[Optional[dict]] = mapped_column(JSON)
    certification_requirements: Mapped[Optional[dict]] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(50), default="active")
    created_by: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=now, onupdate=now)
    chroma_collection: Mapped[Optional[str]] = mapped_column(String(100))


# ──────────────────────────────────────────────────────────────
# CANDIDATES & RESUMES
# ──────────────────────────────────────────────────────────────

class Candidate(Base):
    __tablename__ = "candidates"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    serial_no: Mapped[int] = mapped_column(Integer, unique=True, autoincrement=True, nullable=True)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[Optional[str]] = mapped_column(String(255), unique=True)
    phone: Mapped[Optional[str]] = mapped_column(String(50))
    location: Mapped[Optional[str]] = mapped_column(String(255))
    total_experience_yrs: Mapped[Optional[float]] = mapped_column(Float)
    latest_role: Mapped[Optional[str]] = mapped_column(String(255))
    current_company: Mapped[Optional[str]] = mapped_column(String(255))
    education: Mapped[Optional[dict]] = mapped_column(JSON)
    certifications: Mapped[Optional[dict]] = mapped_column(JSON)
    skills_list: Mapped[Optional[dict]] = mapped_column(JSON)
    domain_text: Mapped[Optional[str]] = mapped_column(Text)
    is_duplicate: Mapped[bool] = mapped_column(Boolean, default=False)
    duplicate_of: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("candidates.id"))
    source: Mapped[str] = mapped_column(String(100), default="upload")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=now, onupdate=now)

    resumes: Mapped[list["Resume"]] = relationship("Resume", back_populates="candidate")
    skills: Mapped[list["CandidateSkill"]] = relationship("CandidateSkill", back_populates="candidate")
    matches: Mapped[list["CandidateJobMatch"]] = relationship("CandidateJobMatch", back_populates="candidate")
    statuses: Mapped[list["CandidateStatus"]] = relationship("CandidateStatus", back_populates="candidate")


class Resume(Base):
    __tablename__ = "resumes"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    candidate_id: Mapped[str] = mapped_column(String(36), ForeignKey("candidates.id", ondelete="CASCADE"))
    original_filename: Mapped[Optional[str]] = mapped_column(String(255))
    file_path: Mapped[str] = mapped_column(Text, nullable=False)
    file_type: Mapped[Optional[str]] = mapped_column(String(10))
    raw_text: Mapped[Optional[str]] = mapped_column(Text)
    parsed_metadata: Mapped[Optional[dict]] = mapped_column(JSON)
    parse_status: Mapped[str] = mapped_column(String(50), default="pending")
    parse_error: Mapped[Optional[str]] = mapped_column(Text)
    chroma_doc_id: Mapped[Optional[str]] = mapped_column(String(100))
    uploaded_by: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("users.id"))
    uploaded_at: Mapped[datetime] = mapped_column(DateTime, default=now)

    candidate: Mapped["Candidate"] = relationship("Candidate", back_populates="resumes")


class CandidateSkill(Base):
    __tablename__ = "candidate_skills"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    candidate_id: Mapped[str] = mapped_column(String(36), ForeignKey("candidates.id", ondelete="CASCADE"))
    skill: Mapped[str] = mapped_column(String(100), nullable=False)
    category: Mapped[Optional[str]] = mapped_column(String(50))
    proficiency: Mapped[Optional[str]] = mapped_column(String(50))
    source: Mapped[str] = mapped_column(String(50), default="resume")

    candidate: Mapped["Candidate"] = relationship("Candidate", back_populates="skills")


# ──────────────────────────────────────────────────────────────
# MATCHING & SCORING
# ──────────────────────────────────────────────────────────────

class CandidateJobMatch(Base):
    __tablename__ = "candidate_job_matches"
    __table_args__ = (UniqueConstraint("candidate_id", "jd_id"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    candidate_id: Mapped[str] = mapped_column(String(36), ForeignKey("candidates.id"))
    jd_id: Mapped[int] = mapped_column(Integer, ForeignKey("job_descriptions.id"))
    mandatory_score: Mapped[Optional[float]] = mapped_column(Float)
    secondary_score: Mapped[Optional[float]] = mapped_column(Float)
    experience_score: Mapped[Optional[float]] = mapped_column(Float)
    domain_score: Mapped[Optional[float]] = mapped_column(Float)
    education_score: Mapped[Optional[float]] = mapped_column(Float)
    semantic_score: Mapped[Optional[float]] = mapped_column(Float)
    total_score: Mapped[Optional[float]] = mapped_column(Float)
    tier: Mapped[Optional[str]] = mapped_column(String(50))
    matched_skills: Mapped[Optional[dict]] = mapped_column(JSON)
    missing_skills: Mapped[Optional[dict]] = mapped_column(JSON)
    risk_flags: Mapped[Optional[dict]] = mapped_column(JSON)
    match_explanation: Mapped[Optional[str]] = mapped_column(Text)
    score_breakdown_json: Mapped[Optional[dict]] = mapped_column(JSON)
    is_shortlisted: Mapped[bool] = mapped_column(Boolean, default=False)
    shortlisted_by: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("users.id"))
    shortlisted_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)

    candidate: Mapped["Candidate"] = relationship("Candidate", back_populates="matches")
    jd: Mapped["JobDescription"] = relationship("JobDescription")


# ──────────────────────────────────────────────────────────────
# CANDIDATE LIFECYCLE
# ──────────────────────────────────────────────────────────────

class CandidateStatus(Base):
    __tablename__ = "candidate_status"
    __table_args__ = (UniqueConstraint("candidate_id", "jd_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    candidate_id: Mapped[str] = mapped_column(String(36), ForeignKey("candidates.id"))
    jd_id: Mapped[int] = mapped_column(Integer, ForeignKey("job_descriptions.id"))
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="New")

    candidate: Mapped["Candidate"] = relationship("Candidate", back_populates="statuses")


class StatusHistory(Base):
    __tablename__ = "status_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    candidate_id: Mapped[str] = mapped_column(String(36), ForeignKey("candidates.id"))
    jd_id: Mapped[int] = mapped_column(Integer, ForeignKey("job_descriptions.id"))
    from_status: Mapped[Optional[str]] = mapped_column(String(50))
    to_status: Mapped[str] = mapped_column(String(50), nullable=False)
    reason: Mapped[Optional[str]] = mapped_column(Text)
    changed_by: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("users.id"))
    changed_at: Mapped[datetime] = mapped_column(DateTime, default=now)


# ──────────────────────────────────────────────────────────────
# PANEL ASSIGNMENTS
# ──────────────────────────────────────────────────────────────

class PanelAssignment(Base):
    __tablename__ = "panel_assignments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    panel_user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"))
    candidate_id: Mapped[str] = mapped_column(String(36), ForeignKey("candidates.id"))
    jd_id: Mapped[int] = mapped_column(Integer, ForeignKey("job_descriptions.id"))
    interview_stage: Mapped[Optional[str]] = mapped_column(String(50))
    assigned_by: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("users.id"))
    assigned_at: Mapped[datetime] = mapped_column(DateTime, default=now)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


# ──────────────────────────────────────────────────────────────
# INTERVIEWS & FEEDBACK
# ──────────────────────────────────────────────────────────────

class Interview(Base):
    __tablename__ = "interviews"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    candidate_id: Mapped[str] = mapped_column(String(36), ForeignKey("candidates.id"))
    jd_id: Mapped[int] = mapped_column(Integer, ForeignKey("job_descriptions.id"))
    panel_user_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("users.id"))
    stage: Mapped[Optional[str]] = mapped_column(String(50))
    scheduled_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    status: Mapped[str] = mapped_column(String(50), default="pending")
    created_by: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)

    feedback: Mapped[list["InterviewFeedback"]] = relationship("InterviewFeedback", back_populates="interview")
    schedule: Mapped[Optional["InterviewSchedule"]] = relationship("InterviewSchedule", back_populates="interview", uselist=False)


class InterviewFeedback(Base):
    __tablename__ = "interview_feedback"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    interview_id: Mapped[str] = mapped_column(String(36), ForeignKey("interviews.id"))
    candidate_id: Mapped[str] = mapped_column(String(36), ForeignKey("candidates.id"))
    panel_user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"))
    technical_rating: Mapped[Optional[int]] = mapped_column(Integer)
    communication_rating: Mapped[Optional[int]] = mapped_column(Integer)
    problem_solving_rating: Mapped[Optional[int]] = mapped_column(Integer)
    cultural_fit_rating: Mapped[Optional[int]] = mapped_column(Integer)
    overall_rating: Mapped[Optional[int]] = mapped_column(Integer)
    recommendation: Mapped[Optional[str]] = mapped_column(String(100))
    rejection_reason: Mapped[Optional[str]] = mapped_column(Text)
    strengths: Mapped[Optional[str]] = mapped_column(Text)
    areas_of_improvement: Mapped[Optional[str]] = mapped_column(Text)
    comments: Mapped[Optional[str]] = mapped_column(Text)
    llm_analysis: Mapped[Optional[dict]] = mapped_column(JSON)
    submitted_at: Mapped[datetime] = mapped_column(DateTime, default=now)

    interview: Mapped["Interview"] = relationship("Interview", back_populates="feedback")


# ──────────────────────────────────────────────────────────────
# INTERVIEW SCHEDULING (MS GRAPH)
# ──────────────────────────────────────────────────────────────

class InterviewSchedule(Base):
    __tablename__ = "interview_schedules"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    candidate_id: Mapped[str] = mapped_column(String(36), ForeignKey("candidates.id"))
    jd_id: Mapped[int] = mapped_column(Integer, ForeignKey("job_descriptions.id"))
    interview_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("interviews.id"))
    organizer_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"))
    attendees: Mapped[Optional[dict]] = mapped_column(JSON)
    scheduled_start: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    scheduled_end: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    timezone: Mapped[str] = mapped_column(String(50), default="UTC")
    graph_event_id: Mapped[Optional[str]] = mapped_column(String(255))
    graph_meeting_id: Mapped[Optional[str]] = mapped_column(String(255))
    teams_join_url: Mapped[Optional[str]] = mapped_column(Text)
    location: Mapped[Optional[str]] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(50), default="scheduled")
    cancel_reason: Mapped[Optional[str]] = mapped_column(Text)
    rescheduled_from: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("interview_schedules.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=now, onupdate=now)

    interview: Mapped[Optional["Interview"]] = relationship("Interview", back_populates="schedule")


# ──────────────────────────────────────────────────────────────
# PANEL AVAILABILITY & CANDIDATE SLOT BOOKING
# ──────────────────────────────────────────────────────────────

class PanelAvailabilitySlot(Base):
    """A time slot that a panel member has declared as available for interviews."""
    __tablename__ = "panel_availability_slots"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    panel_user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False)
    jd_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("job_descriptions.id"))
    slot_start: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    slot_end: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    # available | booked | cancelled
    status: Mapped[str] = mapped_column(String(20), default="available", nullable=False)
    created_by: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)
    # version column used for optimistic locking to prevent double-booking
    version: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    bookings: Mapped[list["SlotBooking"]] = relationship("SlotBooking", back_populates="slot")


class SlotBooking(Base):
    """Records which candidate booked a specific panel availability slot."""
    __tablename__ = "slot_bookings"
    __table_args__ = (UniqueConstraint("slot_id", name="uq_slot_booking_slot"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    slot_id: Mapped[str] = mapped_column(String(36), ForeignKey("panel_availability_slots.id"), nullable=False)
    candidate_id: Mapped[str] = mapped_column(String(36), ForeignKey("candidates.id"), nullable=False)
    jd_id: Mapped[int] = mapped_column(Integer, ForeignKey("job_descriptions.id"), nullable=False)
    interview_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("interviews.id"))
    booked_by: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("users.id"))
    booked_at: Mapped[datetime] = mapped_column(DateTime, default=now)
    notes: Mapped[Optional[str]] = mapped_column(Text)

    slot: Mapped["PanelAvailabilitySlot"] = relationship("PanelAvailabilitySlot", back_populates="bookings")


# ──────────────────────────────────────────────────────────────
# AUDIT LOGS
# ──────────────────────────────────────────────────────────────

class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("users.id"))
    user_role: Mapped[Optional[str]] = mapped_column(String(50))
    action: Mapped[str] = mapped_column(String(100), nullable=False)
    entity_type: Mapped[Optional[str]] = mapped_column(String(100))
    entity_id: Mapped[Optional[str]] = mapped_column(String(255))
    payload: Mapped[Optional[dict]] = mapped_column(JSON)
    ip_address: Mapped[Optional[str]] = mapped_column(String(50))
    user_agent: Mapped[Optional[str]] = mapped_column(Text)
    outcome: Mapped[Optional[str]] = mapped_column(String(50))
    error_msg: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)
