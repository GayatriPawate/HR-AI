from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from groq import AsyncGroq

from app.db.models import JobDescription
from app.agents.jd_analyzer import JDAnalyzerAgent
from app.agents.rubric_agent import RubricAgent
from app.rag.indexer import index_jd


class JDService:
    def __init__(self, db: AsyncSession, openai_client: AsyncGroq):
        self.db = db
        self.openai = openai_client
        self.jd_analyzer = JDAnalyzerAgent(openai_client)
        self.rubric_agent = RubricAgent(openai_client)

    async def create_and_analyze(
        self,
        title: str,
        raw_text: str,
        created_by: str,
    ) -> dict:
        # Create JD record
        jd = JobDescription(
            title=title,
            raw_text=raw_text,
            status="analyzing",
            created_by=created_by,
        )
        self.db.add(jd)
        await self.db.commit()
        await self.db.refresh(jd)

        # Analyze with LLM
        try:
            analysis = await self.jd_analyzer.analyze(raw_text)
            rubric = await self.rubric_agent.build_rubric(analysis)

            jd.title = analysis.get("job_title", title)
            jd.mandatory_skills = analysis.get("mandatory_skills", [])
            jd.secondary_skills = analysis.get("secondary_skills", [])
            jd.nice_to_have = analysis.get("nice_to_have", [])
            jd.min_experience_yrs = analysis.get("min_experience_yrs")
            jd.max_experience_yrs = analysis.get("max_experience_yrs")
            jd.domain = analysis.get("domain")
            jd.industry = analysis.get("industry")
            jd.soft_skills = analysis.get("soft_skills", [])
            jd.synonym_map = analysis.get("synonym_map", {})
            jd.education_requirements = analysis.get("education_requirements", {})
            jd.certification_requirements = analysis.get("certification_requirements", [])
            jd.rubric = rubric
            jd.status = "active"

            await self.db.commit()
            await self.db.refresh(jd)

            # Index JD in ChromaDB
            try:
                await index_jd(jd.id, raw_text, self.openai)
                jd.chroma_collection = f"jd_{jd.id}"
                await self.db.commit()
            except Exception:
                pass

        except Exception as e:
            jd.status = "needs_review"
            await self.db.commit()
            raise RuntimeError(f"JD analysis failed: {e}")

        return self._jd_dict(jd)

    async def get_jd(self, jd_id: int) -> dict | None:
        result = await self.db.execute(
            select(JobDescription).where(JobDescription.id == jd_id)
        )
        jd = result.scalar_one_or_none()
        return self._jd_dict(jd) if jd else None

    async def list_jds(self, status: str | None = None) -> list[dict]:
        query = select(JobDescription)
        if status:
            query = query.where(JobDescription.status == status)
        result = await self.db.execute(query.order_by(JobDescription.created_at.desc()))
        return [self._jd_dict(j) for j in result.scalars().all()]

    def _jd_dict(self, jd: JobDescription) -> dict:
        return {
            "id": jd.id,
            "title": jd.title,
            "raw_text": jd.raw_text,
            "mandatory_skills": jd.mandatory_skills or [],
            "secondary_skills": jd.secondary_skills or [],
            "nice_to_have": jd.nice_to_have or [],
            "min_experience_yrs": jd.min_experience_yrs,
            "domain": jd.domain,
            "industry": jd.industry,
            "soft_skills": jd.soft_skills or [],
            "synonym_map": jd.synonym_map or {},
            "rubric": jd.rubric,
            "education_requirements": jd.education_requirements or {},
            "certification_requirements": jd.certification_requirements or [],
            "status": jd.status,
            "created_at": jd.created_at.isoformat() if jd.created_at else None,
        }
