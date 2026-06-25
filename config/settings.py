from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # App
    app_env: str = "development"
    app_secret_key: str = "dev-secret-key-change-in-production"
    debug: bool = True

    # Database
    database_url: str = "sqlite+aiosqlite:///./hr_platform.db"

    # JWT
    jwt_secret_key: str = "jwt-secret-change-in-production"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 480

    # Groq LLM (free tier)
    groq_api_key: str = ""
    groq_model: str = "llama-3.3-70b-versatile"      # best free model for structured output
    groq_fast_model: str = "llama3-8b-8192"           # fast model for lighter tasks

    # Local embeddings (sentence-transformers — no API key needed)
    embedding_model: str = "all-MiniLM-L6-v2"        # 384 dims, fast on CPU
    embedding_dim: int = 384

    # ChromaDB (local, free)
    chroma_persist_path: str = "./chroma_data"
    chroma_host: str = ""
    chroma_port: int = 8002

    # Microsoft Graph
    azure_tenant_id: str = ""
    azure_client_id: str = ""
    azure_client_secret: str = ""
    graph_organizer_email: str = ""

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # File Storage
    upload_dir: str = "./uploads/resumes"

    # Scoring
    score_highly_suitable: float = 80.0
    score_suitable: float = 60.0
    score_manual_review: float = 40.0
    score_shortlist_threshold: float = 60.0

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


@lru_cache()
def get_settings() -> Settings:
    return Settings()
