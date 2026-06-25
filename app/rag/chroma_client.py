import chromadb
from chromadb.config import Settings as ChromaSettings
from config.settings import get_settings
from functools import lru_cache

settings = get_settings()

RESUME_COLLECTION = "resumes"
JD_COLLECTION_PREFIX = "jd_"


@lru_cache()
def get_chroma_client() -> chromadb.Client:
    if settings.chroma_host:
        return chromadb.HttpClient(
            host=settings.chroma_host,
            port=settings.chroma_port,
        )
    return chromadb.PersistentClient(
        path=settings.chroma_persist_path,
        settings=ChromaSettings(anonymized_telemetry=False),
    )


def get_resume_collection():
    client = get_chroma_client()
    return client.get_or_create_collection(
        name=RESUME_COLLECTION,
        metadata={"hnsw:space": "cosine"},
    )


def get_jd_collection(jd_id: int):
    client = get_chroma_client()
    return client.get_or_create_collection(
        name=f"{JD_COLLECTION_PREFIX}{jd_id}",
        metadata={"hnsw:space": "cosine"},
    )
