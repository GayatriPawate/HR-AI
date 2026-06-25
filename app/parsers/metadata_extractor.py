import json
from groq import AsyncGroq
from config.settings import get_settings

settings = get_settings()

EXTRACTION_PROMPT = """
You are an expert HR data extractor. Extract structured information from the resume text below.

Return a JSON object with EXACTLY this schema:
{
  "name": "Full name of candidate",
  "email": "email address or null",
  "phone": "phone number or null",
  "location": "city/country or null",
  "total_experience_yrs": 5.5,
  "latest_role": "Most recent job title or null",
  "current_company": "Most recent employer or null",
  "skills": ["Python", "FastAPI", "SQL"],
  "domain_text": "Brief description of the candidate's domain/industry focus",
  "education": [
    {"degree": "Bachelor", "field": "Computer Science", "institution": "MIT", "year": 2018}
  ],
  "certifications": ["AWS Certified Developer", "PMP"],
  "companies": ["Company A", "Company B"],
  "projects": ["Project summary 1"],
  "summary": "2-3 sentence professional summary"
}

Rules:
- skills must be a flat list of specific skills (tools, languages, frameworks, methodologies)
- total_experience_yrs should be calculated from work history dates; use 0 if unclear
- Do not invent information not present in the resume
- Return ONLY valid JSON, no explanation
"""


async def extract_candidate_metadata(raw_text: str, client: AsyncGroq) -> dict:
    truncated = raw_text[:6000]

    for attempt in range(2):
        try:
            response = await client.chat.completions.create(
                model=settings.groq_model,
                messages=[
                    {"role": "system", "content": EXTRACTION_PROMPT},
                    {"role": "user", "content": f"Resume:\n\n{truncated}"},
                ],
                response_format={"type": "json_object"},
                temperature=0.1,
            )
            result = json.loads(response.choices[0].message.content)
            return _validate_and_clean(result)
        except (json.JSONDecodeError, Exception):
            if attempt == 1:
                return _default_metadata()

    return _default_metadata()


def _validate_and_clean(data: dict) -> dict:
    defaults = _default_metadata()
    for key, default_val in defaults.items():
        if key not in data:
            data[key] = default_val
    if not isinstance(data.get("skills"), list):
        data["skills"] = []
    if not isinstance(data.get("education"), list):
        data["education"] = []
    if data.get("total_experience_yrs") is None:
        data["total_experience_yrs"] = 0.0
    return data


def _default_metadata() -> dict:
    return {
        "name": "Unknown",
        "email": None,
        "phone": None,
        "location": None,
        "total_experience_yrs": 0.0,
        "latest_role": None,
        "current_company": None,
        "skills": [],
        "domain_text": "",
        "education": [],
        "certifications": [],
        "companies": [],
        "projects": [],
        "summary": "",
    }
