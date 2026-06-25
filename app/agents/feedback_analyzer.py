import json
from groq import AsyncGroq
from app.prompts.prompts import FEEDBACK_ANALYZER_SYSTEM_PROMPT
from config.settings import get_settings

settings = get_settings()


class FeedbackAnalyzerAgent:
    def __init__(self, client: AsyncGroq):
        self.client = client

    async def analyze(self, feedback: dict) -> dict:
        payload = json.dumps(feedback)[:3000]

        for attempt in range(2):
            try:
                response = await self.client.chat.completions.create(
                    model=settings.groq_model,
                    messages=[
                        {"role": "system", "content": FEEDBACK_ANALYZER_SYSTEM_PROMPT},
                        {"role": "user", "content": f"Analyze this interview feedback:\n\n{payload}"},
                    ],
                    response_format={"type": "json_object"},
                    temperature=0.1,
                )
                return json.loads(response.choices[0].message.content)
            except Exception:
                if attempt == 1:
                    return {
                        "sentiment": "neutral",
                        "overall_signal": "neutral",
                        "key_themes": [],
                        "strength_indicators": [],
                        "concern_indicators": [],
                        "flag_for_review": False,
                        "flag_reasons": [],
                        "summary": "Analysis unavailable.",
                    }
        return {}
