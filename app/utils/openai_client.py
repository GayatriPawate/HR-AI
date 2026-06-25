from groq import AsyncGroq
from config.settings import get_settings
from functools import lru_cache

settings = get_settings()


@lru_cache()
def _get_groq_client() -> AsyncGroq:
    if not settings.groq_api_key or settings.groq_api_key.startswith("gsk_your"):
        raise RuntimeError(
            "GROQ_API_KEY not set. Get a free key at https://console.groq.com "
            "and add it to your .env file."
        )
    return AsyncGroq(api_key=settings.groq_api_key)


async def get_openai_client() -> AsyncGroq:
    """Returns AsyncGroq client. Function name kept for backward compatibility."""
    return _get_groq_client()
