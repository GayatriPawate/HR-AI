import re
from groq import AsyncGroq
from app.rag.chroma_client import get_resume_collection, get_jd_collection
from app.rag.embeddings import embed_batch

CHUNK_SIZE = 500  # approximate tokens
CHUNK_OVERLAP = 50


def _split_by_sections(text: str) -> list[dict]:
    section_headers = re.compile(
        r'\n\s*(EXPERIENCE|EDUCATION|SKILLS|CERTIFICATIONS|PROJECTS|SUMMARY|OBJECTIVE'
        r'|WORK HISTORY|EMPLOYMENT|ACHIEVEMENTS|PUBLICATIONS)\s*\n',
        re.IGNORECASE,
    )
    parts = section_headers.split(text)
    chunks = []

    if len(parts) <= 1:
        return _split_by_tokens(text, "general")

    for i, part in enumerate(parts):
        if not part.strip():
            continue
        chunk_type = "general"
        if i > 0:
            header = parts[i - 1].strip().lower() if i > 0 else ""
            if any(k in header for k in ("skill",)):
                chunk_type = "skills"
            elif any(k in header for k in ("experience", "work", "employment")):
                chunk_type = "experience"
            elif any(k in header for k in ("education",)):
                chunk_type = "education"
            elif any(k in header for k in ("project",)):
                chunk_type = "projects"
            elif any(k in header for k in ("cert",)):
                chunk_type = "education"
            elif any(k in header for k in ("summary", "objective")):
                chunk_type = "summary"

        sub_chunks = _split_by_tokens(part.strip(), chunk_type)
        chunks.extend(sub_chunks)

    return chunks


def _split_by_tokens(text: str, chunk_type: str) -> list[dict]:
    words = text.split()
    chunks = []
    for i in range(0, len(words), CHUNK_SIZE - CHUNK_OVERLAP):
        chunk_words = words[i: i + CHUNK_SIZE]
        chunks.append({"text": " ".join(chunk_words), "type": chunk_type})
    return chunks


async def index_resume(
    resume_id: str,
    candidate_id: str,
    raw_text: str,
    metadata: dict,
    openai_client: AsyncGroq,
) -> str:
    collection = get_resume_collection()
    chunks = _split_by_sections(raw_text)

    if not chunks:
        return f"resume_{resume_id}_0"

    texts = [c["text"] for c in chunks]
    embeddings = await embed_batch(texts, openai_client)

    ids = [f"resume_{resume_id}_chunk_{i}" for i in range(len(chunks))]
    metas = [
        {
            "candidate_id": candidate_id,
            "resume_id": resume_id,
            "candidate_name": metadata.get("name", "Unknown"),
            "candidate_email": (metadata.get("email") or "").lower().strip(),
            "candidate_phone": metadata.get("phone") or "",
            "chunk_type": chunks[i]["type"],
            "chunk_index": i,
            "total_chunks": len(chunks),
        }
        for i in range(len(chunks))
    ]

    collection.upsert(ids=ids, embeddings=embeddings, documents=texts, metadatas=metas)
    return ids[0]


async def index_jd(jd_id: int, raw_text: str, openai_client: AsyncGroq) -> str:
    collection = get_jd_collection(jd_id)
    chunks = _split_by_tokens(raw_text, "jd")

    if not chunks:
        return f"jd_{jd_id}_chunk_0"

    texts = [c["text"] for c in chunks]
    embeddings = await embed_batch(texts, openai_client)

    ids = [f"jd_{jd_id}_chunk_{i}" for i in range(len(chunks))]
    metas = [{"jd_id": jd_id, "chunk_index": i} for i in range(len(chunks))]

    collection.upsert(ids=ids, embeddings=embeddings, documents=texts, metadatas=metas)
    return ids[0]
