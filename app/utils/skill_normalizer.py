from rapidfuzz import fuzz

SYNONYM_MAP = {
    "ml": ["machine learning", "artificial intelligence", "ai"],
    "dl": ["deep learning"],
    "nlp": ["natural language processing"],
    "k8s": ["kubernetes"],
    "js": ["javascript"],
    "ts": ["typescript"],
    "py": ["python"],
    "pg": ["postgresql", "postgres"],
    "tf": ["tensorflow"],
    "pt": ["pytorch"],
    "aws": ["amazon web services"],
    "gcp": ["google cloud platform", "google cloud"],
    "ci/cd": ["continuous integration", "devops", "jenkins", "github actions"],
}


def normalize_skill(skill: str) -> str:
    return skill.lower().strip()


def expand_synonyms(skill: str, custom_map: dict | None = None) -> list[str]:
    normalized = normalize_skill(skill)
    variants = [normalized]

    combined = {**SYNONYM_MAP, **(custom_map or {})}
    for key, synonyms in combined.items():
        if normalized == key or normalized in synonyms:
            variants.extend([key] + synonyms)

    return list(set(variants))


def fuzzy_match(skill1: str, skill2: str, threshold: int = 85) -> bool:
    return fuzz.ratio(normalize_skill(skill1), normalize_skill(skill2)) >= threshold
