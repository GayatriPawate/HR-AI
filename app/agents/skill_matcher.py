import json
from groq import AsyncGroq
from app.prompts.prompts import SKILL_MATCHER_SYSTEM_PROMPT
from config.settings import get_settings

settings = get_settings()


class SkillMatcherAgent:
    def __init__(self, client: AsyncGroq):
        self.client = client

    async def explain_match(
        self,
        candidate_profile: dict,
        jd_rubric: dict,
        computed_scores: dict,
    ) -> dict:
        payload = json.dumps({
            "candidate_profile": candidate_profile,
            "jd_rubric": jd_rubric,
            "computed_scores": computed_scores,
        }, indent=2)[:5000]

        for attempt in range(2):
            try:
                response = await self.client.chat.completions.create(
                    model=settings.groq_model,
                    messages=[
                        {"role": "system", "content": SKILL_MATCHER_SYSTEM_PROMPT},
                        {"role": "user", "content": payload},
                    ],
                    response_format={"type": "json_object"},
                    temperature=0.2,
                )
                return json.loads(response.choices[0].message.content)
            except Exception:
                if attempt == 1:
                    return {
                        "match_explanation": "Explanation unavailable.",
                        "nuanced_flags": [],
                        "recommendation_note": "",
                    }
        return {}
