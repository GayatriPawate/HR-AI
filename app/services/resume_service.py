import uuid
import re
from pathlib import Path
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, func
from groq import AsyncGroq

from app.db.models import Candidate, Resume, CandidateSkill, CandidateStatus
from app.parsers.pdf_parser import extract_text_from_pdf
from app.parsers.docx_parser import extract_text_from_docx
from app.parsers.metadata_extractor import extract_candidate_metadata
from app.rag.indexer import index_resume
from config.settings import get_settings

settings = get_settings()

# Namespace UUID for deterministic candidate ID generation
_CANDIDATE_NS = uuid.UUID("a1b2c3d4-e5f6-7890-abcd-ef1234567890")


def _normalize_phone(phone: str | None) -> str | None:
    """Strip all non-digit chars; return None if fewer than 7 digits remain."""
    if not phone:
        return None
    digits = re.sub(r"\D", "", phone)
    return digits if len(digits) >= 7 else None


def _make_candidate_id(email: str | None, phone: str | None) -> str:
    """
    Generate a deterministic UUID5 from email + phone so the same person
    always gets the same candidate ID across re-uploads.
    Falls back to a random uuid4 only when both are missing.
    """
    email_clean = email.lower().strip() if email else ""
    phone_clean = _normalize_phone(phone) or ""

    if not email_clean and not phone_clean:
        return str(uuid.uuid4())

    key = f"{email_clean}|{phone_clean}"
    return str(uuid.uuid5(_CANDIDATE_NS, key))


class ResumeService:
    def __init__(self, db: AsyncSession, openai_client: AsyncGroq):
        self.db = db
        self.openai = openai_client

    async def ingest_file(
        self,
        filename: str,
        file_bytes: bytes,
        uploaded_by: str,
        jd_id: int | None = None,
    ) -> dict:
        suffix = Path(filename).suffix.lower().lstrip(".")
        try:
            if suffix == "pdf":
                raw_text = extract_text_from_pdf(file_bytes)
            elif suffix in ("docx", "doc"):
                raw_text = extract_text_from_docx(file_bytes)
            else:
                return {"filename": filename, "status": "failed", "error": f"Unsupported type: {suffix}"}
        except Exception as e:
            return {"filename": filename, "status": "failed", "error": str(e)}

        metadata = await extract_candidate_metadata(raw_text, self.openai)

        # Build deterministic candidate ID from email + phone
        email_clean = metadata.get("email", "").lower().strip() or None
        phone_clean = _normalize_phone(metadata.get("phone"))
        candidate_id = _make_candidate_id(email_clean, phone_clean)

        # Deduplication: check by deterministic ID first, then email, then phone
        is_duplicate = False
        conditions = [Candidate.id == candidate_id]
        if email_clean:
            conditions.append(Candidate.email == email_clean)
        if phone_clean:
            conditions.append(Candidate.phone == phone_clean)

        result = await self.db.execute(
            select(Candidate).where(or_(*conditions))
        )
        existing = result.scalars().first()
        if existing:
            candidate_id = existing.id
            is_duplicate = True

        if not is_duplicate:
            count_result = await self.db.execute(select(func.count()).select_from(Candidate))
            next_serial = (count_result.scalar() or 0) + 1

            candidate = Candidate(
                id=candidate_id,
                serial_no=next_serial,
                full_name=metadata.get("name", "Unknown"),
                email=email_clean,
                phone=metadata.get("phone"),
                location=metadata.get("location"),
                total_experience_yrs=float(metadata.get("total_experience_yrs") or 0),
                latest_role=metadata.get("latest_role"),
                current_company=metadata.get("current_company"),
                education=metadata.get("education", []),
                certifications=metadata.get("certifications", []),
                skills_list=metadata.get("skills", []),
                domain_text=metadata.get("domain_text", ""),
            )
            self.db.add(candidate)

            # Store skills
            for skill in metadata.get("skills", []):
                self.db.add(CandidateSkill(
                    candidate_id=candidate_id,
                    skill=skill,
                    category="technical",
                    source="resume",
                ))

        # Save file
        file_path = self._save_file(filename, file_bytes, candidate_id)

        resume_id = str(uuid.uuid4())
        resume = Resume(
            id=resume_id,
            candidate_id=candidate_id,
            original_filename=filename,
            file_path=file_path,
            file_type=suffix,
            raw_text=raw_text,
            parsed_metadata=metadata,
            parse_status="success",
            uploaded_by=uploaded_by,
        )
        self.db.add(resume)

        # Set initial status if JD provided
        if jd_id and not is_duplicate:
            self.db.add(CandidateStatus(
                candidate_id=candidate_id,
                jd_id=jd_id,
                status="New",
            ))

        await self.db.commit()

        # Index in ChromaDB (async, after commit)
        try:
            chroma_doc_id = await index_resume(
                resume_id=resume_id,
                candidate_id=candidate_id,
                raw_text=raw_text,
                metadata=metadata,
                openai_client=self.openai,
            )
            resume.chroma_doc_id = chroma_doc_id
            await self.db.commit()
        except Exception as e:
            # Indexing failure is non-fatal; candidate still saved
            pass

        return {
            "filename": filename,
            "status": "success",
            "candidate_id": candidate_id,
            "candidate_name": metadata.get("name", "Unknown"),
            "is_duplicate": is_duplicate,
            "skills_found": len(metadata.get("skills", [])),
        }

    def _save_file(self, filename: str, file_bytes: bytes, candidate_id: str) -> str:
        upload_dir = Path(settings.upload_dir)
        upload_dir.mkdir(parents=True, exist_ok=True)
        safe_name = f"{candidate_id}_{Path(filename).name}"
        file_path = upload_dir / safe_name
        file_path.write_bytes(file_bytes)
        return str(file_path)

    async def get_candidates(
        self,
        jd_id: int | None = None,
        status: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[dict]:
        from sqlalchemy import desc
        from app.db.models import CandidateJobMatch

        if jd_id:
            query = (
                select(Candidate, CandidateJobMatch)
                .join(CandidateJobMatch, Candidate.id == CandidateJobMatch.candidate_id)
                .where(CandidateJobMatch.jd_id == jd_id)
                .order_by(desc(CandidateJobMatch.total_score))
                .limit(limit).offset(offset)
            )
            results = await self.db.execute(query)
            rows = results.all()
            return [
                {
                    **self._candidate_dict(row[0]),
                    "total_score": row[1].total_score,
                    "tier": row[1].tier,
                    "matched_skills": row[1].matched_skills,
                    "missing_skills": row[1].missing_skills,
                    "risk_flags": row[1].risk_flags,
                    "is_shortlisted": row[1].is_shortlisted,
                }
                for row in rows
            ]
        else:
            result = await self.db.execute(
                select(Candidate).limit(limit).offset(offset)
            )
            return [self._candidate_dict(c) for c in result.scalars().all()]

    def _candidate_dict(self, c: Candidate) -> dict:
        return {
            "id": c.id,
            "full_name": c.full_name,
            "email": c.email,
            "phone": c.phone,
            "location": c.location,
            "total_experience_yrs": c.total_experience_yrs,
            "latest_role": c.latest_role,
            "current_company": c.current_company,
            "skills_list": c.skills_list or [],
            "education": c.education or [],
            "certifications": c.certifications or [],
            "domain_text": c.domain_text,
        }
