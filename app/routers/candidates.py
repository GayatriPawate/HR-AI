from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from groq import AsyncGroq

from app.db.base import get_db
from app.auth.rbac import role_required, require_any
from app.services.matching_service import MatchingService
from app.services.dashboard_service import DashboardService
from app.models.schemas import MatchRequest, StatusUpdate, ShortlistRequest, CandidateChatRequest
from app.utils.openai_client import get_openai_client
from app.rag.retriever import search_candidates_for_jd
from app.db.models import JobDescription

router = APIRouter(prefix="/candidates", tags=["candidates"])


@router.get("/shortlisted")
async def get_shortlisted(
    jd_id: int | None = None,
    current_user: dict = Depends(role_required("admin")),
    db: AsyncSession = Depends(get_db),
):
    from sqlalchemy import select as sa_select
    from app.db.models import Candidate, CandidateJobMatch
    query = (
        sa_select(Candidate, CandidateJobMatch)
        .join(CandidateJobMatch, Candidate.id == CandidateJobMatch.candidate_id)
        .where(CandidateJobMatch.is_shortlisted == True)
    )
    if jd_id:
        query = query.where(CandidateJobMatch.jd_id == jd_id)
    result = await db.execute(query)
    rows = result.all()
    return [
        {
            "candidate_id": row[0].id,
            "serial_no": f"C{str(row[0].serial_no).zfill(3)}" if row[0].serial_no else "—",
            "full_name": row[0].full_name,
            "jd_id": row[1].jd_id,
            "total_score": row[1].total_score,
            "tier": row[1].tier,
        }
        for row in rows
    ]


@router.post("/match")
async def run_matching(
    payload: MatchRequest,
    current_user: dict = Depends(role_required("admin")),
    db: AsyncSession = Depends(get_db),
    openai_client: AsyncGroq = Depends(get_openai_client),
):
    service = MatchingService(db, openai_client)
    results = await service.match_all_candidates_for_jd(payload.jd_id)
    return {"jd_id": payload.jd_id, "total_matched": len(results), "results": results}


@router.get("/ranked")
async def get_ranked(
    jd_id: int,
    tier: str | None = None,
    min_score: float = 0,
    limit: int = 50,
    offset: int = 0,
    current_user: dict = Depends(role_required("admin")),
    db: AsyncSession = Depends(get_db),
    openai_client: AsyncGroq = Depends(get_openai_client),
):
    service = MatchingService(db, openai_client)
    return await service.get_ranked_candidates(jd_id, tier, min_score, limit, offset)


@router.post("/{candidate_id}/shortlist")
async def shortlist_candidate(
    candidate_id: str,
    payload: ShortlistRequest,
    current_user: dict = Depends(role_required("admin")),
    db: AsyncSession = Depends(get_db),
    openai_client: AsyncGroq = Depends(get_openai_client),
):
    service = MatchingService(db, openai_client)
    success = await service.shortlist_candidate(candidate_id, payload.jd_id, current_user["sub"])
    if not success:
        raise HTTPException(status_code=404, detail="Match record not found")
    return {"status": "shortlisted"}


@router.post("/{candidate_id}/status")
@router.patch("/{candidate_id}/status")
async def update_status(
    candidate_id: str,
    payload: StatusUpdate,
    current_user: dict = Depends(role_required("admin")),
    db: AsyncSession = Depends(get_db),
):
    service = DashboardService(db)
    await service.update_candidate_status(
        candidate_id=candidate_id,
        jd_id=payload.jd_id,
        new_status=payload.status,
        changed_by=current_user["sub"],
        reason=payload.reason or "",
    )
    return {"status": "updated", "new_status": payload.status}


@router.get("/{candidate_id}")
async def get_candidate_detail(
    candidate_id: str,
    jd_id: int | None = None,
    current_user: dict = Depends(require_any),
    db: AsyncSession = Depends(get_db),
):
    service = DashboardService(db)
    detail = await service.get_candidate_detail(candidate_id, jd_id)
    if not detail:
        raise HTTPException(status_code=404, detail="Candidate not found")

    # Panel users: remove sensitive admin-only fields
    if current_user.get("role") == "panel":
        detail.pop("status_history", None)
        if "match" in detail and detail["match"]:
            detail["match"].pop("risk_flags", None)

    return detail


@router.post("/chat")
async def chat_with_cvs(
    payload: CandidateChatRequest,
    current_user: dict = Depends(role_required("admin")),
    db: AsyncSession = Depends(get_db),
    openai_client: AsyncGroq = Depends(get_openai_client),
):
    """
    HR asks a natural-language question about candidates for a JD.
    Returns an LLM answer grounded in retrieved CV chunks + citations.
    """
    # Fetch JD text for context
    jd_result = await db.execute(select(JobDescription).where(JobDescription.id == payload.jd_id))
    jd = jd_result.scalar_one_or_none()
    if not jd:
        raise HTTPException(status_code=404, detail="JD not found")

    # RAG: retrieve top CV chunks most relevant to the question
    hits = await search_candidates_for_jd(
        jd_text=payload.question,          # use the question as the query
        openai_client=openai_client,
        top_k=payload.top_k,
    )

    if not hits:
        return {
            "answer": "No candidate CV data found in the index. Please run AI Matching first to index resumes.",
            "citations": [],
        }

    # Build context block from retrieved chunks
    context_parts = []
    for i, hit in enumerate(hits, 1):
        context_parts.append(
            f"[{i}] Candidate: {hit.get('candidate_name') or hit['candidate_id']}\n"
            f"Excerpt: {hit['top_chunk']}\n"
            f"Similarity: {hit['similarity']:.2f}"
        )
    context_block = "\n\n".join(context_parts)

    system_prompt = (
        "You are an expert HR assistant helping a hiring manager evaluate candidates. "
        "You are given excerpts from candidate CVs retrieved from a vector database. "
        "Answer the HR's question using ONLY the provided CV excerpts. "
        "When referencing a candidate use their name and cite the excerpt number like [1], [2]. "
        "Be concise, factual, and highlight differences between candidates where relevant. "
        "If you cannot answer from the provided excerpts, say so."
    )

    user_message = (
        f"Job Description: {jd.title}\n\n"
        f"CV Excerpts:\n{context_block}\n\n"
        f"HR Question: {payload.question}"
    )

    response = await openai_client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user",   "content": user_message},
        ],
        temperature=0.3,
        max_tokens=1024,
    )

    answer = response.choices[0].message.content.strip()

    citations = [
        {
            "candidate_id":   hit["candidate_id"],
            "candidate_name": hit.get("candidate_name"),
            "excerpt":        hit["top_chunk"],
            "similarity":     round(hit["similarity"], 3),
        }
        for hit in hits
    ]

    return {"answer": answer, "citations": citations}


@router.get("/{candidate_id}/score")
async def get_candidate_score(
    candidate_id: str,
    jd_id: int,
    current_user: dict = Depends(require_any),
    db: AsyncSession = Depends(get_db),
):
    service = DashboardService(db)
    detail = await service.get_candidate_detail(candidate_id, jd_id)
    if not detail:
        raise HTTPException(status_code=404, detail="Candidate not found")

    match = detail.get("match")
    if not match:
        raise HTTPException(status_code=404, detail="No match data for this JD")

    return {
        "candidate_id": candidate_id,
        "jd_id": jd_id,
        "total_score": match.get("total_score"),
        "tier": match.get("tier"),
        "score_breakdown": match.get("score_breakdown"),
        "matched_skills": match.get("matched_skills"),
        "missing_skills": match.get("missing_skills"),
        "match_explanation": match.get("match_explanation"),
        # Risk flags: admin only
        **({"risk_flags": match.get("risk_flags")} if current_user.get("role") == "admin" else {}),
    }
