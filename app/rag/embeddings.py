"""
Local embeddings using sentence-transformers.
Free, runs on CPU, no API key needed.
Model (~90MB) is downloaded automatically on first use.
"""
import asyncio
from functools import lru_cache
from config.settings import get_settings

settings = get_settings()

_embed_cache: dict[str, list[float]] = {}


@lru_cache()
def _get_model():
    """Load sentence-transformers model once and cache it."""
    from sentence_transformers import SentenceTransformer
    return SentenceTransformer(settings.embedding_model)


def _encode_sync(texts: list[str]) -> list[list[float]]:
    model = _get_model()
    embeddings = model.encode(texts, convert_to_numpy=True, show_progress_bar=False)
    return [vec.tolist() for vec in embeddings]


async def embed_text(text: str, client=None) -> list[float]:
    """
    Embed a single text string.
    `client` parameter accepted but ignored — embeddings are local.
    """
    key = text[:200]
    if key in _embed_cache:
        return _embed_cache[key]

    loop = asyncio.get_event_loop()
    results = await loop.run_in_executor(None, _encode_sync, [text[:4000]])
    vec = results[0]
    _embed_cache[key] = vec
    return vec


async def embed_batch(texts: list[str], client=None) -> list[list[float]]:
    """
    Embed a list of texts in one local batch call.
    `client` parameter accepted but ignored — embeddings are local.
    """
    truncated = [t[:4000] for t in texts]
    loop = asyncio.get_event_loop()
    results = await loop.run_in_executor(None, _encode_sync, truncated)
    return results


def cosine_similarity(v1: list[float], v2: list[float]) -> float:
    import numpy as np
    a, b = np.array(v1), np.array(v2)
    denom = np.linalg.norm(a) * np.linalg.norm(b)
    if denom == 0:
        return 0.0
    return float(np.dot(a, b) / denom)
