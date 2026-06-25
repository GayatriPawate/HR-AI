import json
from groq import AsyncGroq
from app.prompts.prompts import JD_ANALYZER_SYSTEM_PROMPT
from config.settings import get_settings

settings = get_settings()


class JDAnalyzerAgent:
    def __init__(self, client: AsyncGroq):
        self.client = client

    async def analyze(self, raw_text: str) -> dict:
        for attempt in range(2):
            try:
                response = await self.client.chat.completions.create(
                    model=settings.groq_model,
                    messages=[
                        {"role": "system", "content": JD_ANALYZER_SYSTEM_PROMPT},
                        {"role": "user", "content": f"Analyze this job description:\n\n{raw_text[:6000]}"},
                    ],
                    response_format={"type": "json_object"},
                    temperature=0.1,
                )
                result = json.loads(response.choices[0].message.content)
                self._validate(result)
                return result
            except (json.JSONDecodeError, KeyError, ValueError) as e:
                if attempt == 1:
                    raise RuntimeError(f"JD analysis failed after retry: {e}")
        return {}

    def _validate(self, result: dict):
        required = ["job_title", "mandatory_skills", "secondary_skills"]
        for field in required:
            if field not in result:
                raise KeyError(f"Missing required field: {field}")
        if not isinstance(result["mandatory_skills"], list):
            raise ValueError("mandatory_skills must be a list")
