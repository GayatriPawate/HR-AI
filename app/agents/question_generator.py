import json
from groq import AsyncGroq
from app.prompts.prompts import QUESTION_GENERATOR_SYSTEM_PROMPT
from config.settings import get_settings

settings = get_settings()


class QuestionGeneratorAgent:
    def __init__(self, client: AsyncGroq):
        self.client = client

    async def generate(
        self,
        candidate_profile: dict,
        jd_data: dict,
        score_breakdown: dict,
        categories: list[str] | None = None,
    ) -> list[dict]:
        if categories is None:
            categories = ["conceptual", "practical", "scenario", "technical", "behavioral"]

        payload = {
            "candidate_profile": {
                "name": candidate_profile.get("full_name"),
                "skills": candidate_profile.get("skills_list", []),
                "experience_yrs": candidate_profile.get("total_experience_yrs"),
                "latest_role": candidate_profile.get("latest_role"),
                "domain": candidate_profile.get("domain_text"),
            },
            "jd": {
                "title": jd_data.get("title"),
                "mandatory_skills": jd_data.get("mandatory_skills", []),
                "secondary_skills": jd_data.get("secondary_skills", []),
                "domain": jd_data.get("domain"),
                "soft_skills": jd_data.get("soft_skills", []),
            },
            "score_breakdown": score_breakdown,
            "requested_categories": categories,
        }

        for attempt in range(2):
            try:
                response = await self.client.chat.completions.create(
                    model=settings.groq_model,
                    messages=[
                        {"role": "system", "content": QUESTION_GENERATOR_SYSTEM_PROMPT},
                        {"role": "user", "content": json.dumps(payload)[:5000]},
                    ],
                    temperature=0.7,
                )
                content = response.choices[0].message.content.strip()
                # Handle both raw array and wrapped JSON
                if content.startswith("["):
                    return json.loads(content)
                parsed = json.loads(content)
                if isinstance(parsed, list):
                    return parsed
                if "questions" in parsed:
                    return parsed["questions"]
                return []
            except Exception:
                if attempt == 1:
                    return []
        return []
