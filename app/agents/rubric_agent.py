import json
from groq import AsyncGroq
from app.prompts.prompts import RUBRIC_AGENT_SYSTEM_PROMPT
from config.settings import get_settings

settings = get_settings()


class RubricAgent:
    def __init__(self, client: AsyncGroq):
        self.client = client

    async def build_rubric(self, jd_data: dict) -> dict:
        payload = json.dumps({
            "job_title": jd_data.get("job_title", jd_data.get("title")),
            "mandatory_skills": jd_data.get("mandatory_skills", []),
            "domain": jd_data.get("domain"),
            "soft_skills": jd_data.get("soft_skills", []),
        })[:2000]

        for attempt in range(2):
            try:
                response = await self.client.chat.completions.create(
                    model=settings.groq_model,
                    messages=[
                        {"role": "system", "content": RUBRIC_AGENT_SYSTEM_PROMPT},
                        {"role": "user", "content": f"Build evaluation rubric for:\n{payload}"},
                    ],
                    response_format={"type": "json_object"},
                    temperature=0.2,
                )
                result = json.loads(response.choices[0].message.content)
                return result.get("rubric_categories", result)
            except Exception:
                if attempt == 1:
                    return self._default_rubric()
        return self._default_rubric()

    def _default_rubric(self) -> list:
        return [
            {"category": "Technical Skills", "weight": 40, "scoring_guide": "Depth and breadth of relevant technical skills"},
            {"category": "Domain Knowledge", "weight": 20, "scoring_guide": "Industry and domain understanding"},
            {"category": "Problem Solving", "weight": 25, "scoring_guide": "Approach to complex problems"},
            {"category": "Communication", "weight": 15, "scoring_guide": "Clarity and articulation"},
        ]
