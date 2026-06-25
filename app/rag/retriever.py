from groq import AsyncGroq
from app.rag.chroma_client import get_resume_collection, get_jd_collection
from app.rag.embeddings import embed_text, cosine_similarity


async def get_semantic_similarity(
    candidate_id: str,
    jd_id: int,
    openai_client: AsyncGroq,
) -> float:
    """Compute overall semantic similarity between a candidate's resume and a JD."""
    try:
        resume_collection = get_resume_collection()
        jd_collection = get_jd_collection(jd_id)

        # Get candidate skill chunks
        resume_results = resume_collection.get(
            where={"candidate_id": candidate_id},
            include=["documents"],
        )
        if not resume_results["documents"]:
            return 0.5

        resume_text = " ".join(resume_results["documents"][:5])

        # Get JD text
        jd_results = jd_collection.get(include=["documents"])
        if not jd_results["documents"]:
            return 0.5

        jd_text = " ".join(jd_results["documents"][:3])

        resume_vec = await embed_text(resume_text[:4000], openai_client)
        jd_vec = await embed_text(jd_text[:4000], openai_client)

        return cosine_similarity(resume_vec, jd_vec)
    except Exception:
        return 0.5


async def search_candidates_for_jd(
    jd_text: str,
    openai_client: AsyncGroq,
    top_k: int = 30,
    chunk_type_filter: list[str] | None = None,
) -> list[dict]:
    """Retrieve top matching candidate chunks for a JD query."""
    collection = get_resume_collection()
    query_vec = await embed_text(jd_text[:4000], openai_client)

    where_filter = {}
    if chunk_type_filter:
        where_filter = {"chunk_type": {"$in": chunk_type_filter}}

    results = collection.query(
        query_embeddings=[query_vec],
        n_results=min(top_k, 100),
        where=where_filter if where_filter else None,
        include=["documents", "metadatas", "distances"],
    )

    candidates = {}
    for doc, meta, dist in zip(
        results["documents"][0],
        results["metadatas"][0],
        results["distances"][0],
    ):
        cid = meta.get("candidate_id")
        similarity = 1 - dist  # ChromaDB cosine distance to similarity
        if cid not in candidates or candidates[cid]["similarity"] < similarity:
            candidates[cid] = {
                "candidate_id": cid,
                "candidate_name": meta.get("candidate_name"),
                "similarity": similarity,
                "top_chunk": doc[:300],
            }

    return sorted(candidates.values(), key=lambda x: -x["similarity"])


def delete_candidate_from_index(candidate_id: str):
    collection = get_resume_collection()
    results = collection.get(where={"candidate_id": candidate_id}, include=["documents"])
    if results["ids"]:
        collection.delete(ids=results["ids"])
