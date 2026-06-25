from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import logging

import asyncio
from app.db.base import init_db
from app.rag.embeddings import _get_model
from app.routers import auth, resumes, jd, candidates, interviews, questions, scheduling, dashboard, users, availability, manager

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="HR Multi-Agent Hiring Platform",
    description="AI-powered candidate evaluation, panel support, and interview scheduling",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers
app.include_router(auth.router)
app.include_router(resumes.router)
app.include_router(jd.router)
app.include_router(candidates.router)
app.include_router(interviews.router)
app.include_router(questions.router)
app.include_router(scheduling.router)
app.include_router(dashboard.router)
app.include_router(users.router)
app.include_router(availability.router)
app.include_router(manager.router)


async def _warmup_model():
    """Load the sentence-transformer model in the background — does not block startup."""
    try:
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, _get_model)
        logger.info("Embedding model pre-loaded")
    except Exception as e:
        logger.warning(f"Embedding model warm-up failed (non-fatal): {e}")


@app.on_event("startup")
async def startup():
    await init_db()
    logger.info("Database initialized")
    # Fire model warm-up in background — login and all other endpoints
    # are available immediately; only /candidates/chat needs the model
    asyncio.create_task(_warmup_model())


@app.get("/health")
async def health():
    return {"status": "ok", "service": "HR Hiring Platform API"}


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled error: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"},
    )
