"""
RAG Query service.
Handles retrieval (top_k=30 → rerank to 6), prompt construction,
answer generation, citation building, and full logging.

Supports two retrieval methods:
- "openai": vector search via embeddings + match_knowledge_chunks RPC
- "fulltext": Postgres BM25 fulltext search via search_knowledge_chunks_fulltext RPC

Uses user JWT for retrieval (RLS enforced).
Uses admin client ONLY for logging (insert into knowledge_queries / knowledge_query_chunks).
"""
from __future__ import annotations
import logging
import time
from uuid import UUID, uuid4

logger = logging.getLogger(__name__)

from knowledge_engine.core.config import (
    EMBEDDING_PROVIDER,
    RETRIEVAL_TOP_K,
    RETRIEVAL_SCORE_THRESHOLD,
    WEAK_MATCH_SCORE_THRESHOLD,
)
from knowledge_engine.core.openai_client import chat_completion
from knowledge_engine.core.supabase_client import get_user_supabase, get_admin_supabase
from knowledge_engine.dependencies.auth import extract_user_id_from_jwt
from knowledge_engine.models.schemas import (
    CitationItem,
    QueryResponse,
    RetrievedChunk,
)

# ─── Constants ────────────────────────────────────────────────────────────────

RETRIEVAL_INITIAL_K: int = 30   # Fetch 30 candidates
RERANK_FINAL_K: int = RETRIEVAL_TOP_K  # Rerank down to 6

NO_ANSWER = "ospecificerat i underlaget"

# ─── Mode Prompts ─────────────────────────────────────────────────────────────

MODE_INSTRUCTIONS = {
    "technical": (
        "Du är en teknisk expert på energisystem. Svara med tekniska termer, mätvärden, "
        "integrationskrav, risker, cybersäkerhet och regelverk. Var precis och detaljerad."
    ),
    "sales": (
        "Du är en säljrådgivare. Förklara kundvärde i enkel svenska. Lyft fördelar, "
        "riskkontroll och varför Solpulsen är det bästa valet. Håll det kortfattat och övertygande."
    ),
    "investor": (
        "Du är en affärsanalytiker. Fokusera på marknadspotential, competitive moat, "
        "skalbarhet, compliance, riskprofil och intäktsspår. Var strukturerad och faktabaserad."
    ),
}

SYSTEM_PROMPT_TEMPLATE = """Du är Pulsen A.I. Knowledge Engine, ett internt kunskapssystem för Solpulsen.

{mode_instruction}

REGLER SOM ALDRIG FÅR BRYTAS:
1. Svara ENDAST baserat på den kontext som tillhandahålls nedan.
2. Om informationen saknas i kontexten, skriv exakt: "ospecificerat i underlaget"
3. Inga gissningar, inga antaganden, ingen information utanför kontexten.
4. Skriv alltid på svenska.
5. Ingen fluff. Var koncis och faktabaserad.
6. Avsluta alltid svaret med en källförteckning i formatet:
   KÄLLOR:
   - [Dokumenttitel, version, sida X-Y, Chunk ID: <id>]

KONTEXT:
{context}"""


# ─── Retrieval: Vector Search ────────────────────────────────────────────────

async def _retrieve_vector(
    question: str,
    collection_id: str,
    jwt: str,
) -> list[dict]:
    """
    Embed the question and retrieve top-30 candidates via cosine similarity.
    Uses match_knowledge_chunks RPC. User JWT — RLS enforced.
    """
    from knowledge_engine.core.embeddings import get_embedder
    embedder = get_embedder()
    embedding = await embedder.embed_query(question)
    client = get_user_supabase(jwt)

    result = client.rpc(
        "match_knowledge_chunks",
        {
            "query_embedding": embedding,
            "collection_id_filter": collection_id,
            "match_count": RETRIEVAL_INITIAL_K,
            "score_threshold": RETRIEVAL_SCORE_THRESHOLD,
        },
    ).execute()

    return result.data or []


# ─── Retrieval: Fulltext Search ──────────────────────────────────────────────

async def _retrieve_fulltext(
    question: str,
    collection_id: str,
    jwt: str,
) -> list[dict]:
    """
    Retrieve top-30 candidates via Postgres fulltext search (BM25).
    Uses search_knowledge_chunks_fulltext RPC. User JWT — RLS enforced.
    No embeddings needed.
    """
    client = get_user_supabase(jwt)

    result = client.rpc(
        "search_knowledge_chunks_fulltext",
        {
            "search_query": question,
            "collection_id_filter": collection_id,
            "match_count": RETRIEVAL_INITIAL_K,
        },
    ).execute()

    return result.data or []


# ─── Retrieval Router ────────────────────────────────────────────────────────

async def _retrieve_candidates(
    question: str,
    collection_id: str,
    jwt: str,
) -> list[dict]:
    """
    Route to the correct retrieval method based on EMBEDDING_PROVIDER config.
    - "openai": vector search via embeddings
    - "fulltext": Postgres BM25 fulltext search
    """
    if EMBEDDING_PROVIDER == "fulltext":
        return await _retrieve_fulltext(question, collection_id, jwt)
    else:
        return await _retrieve_vector(question, collection_id, jwt)


def _rerank(candidates: list[dict]) -> list[dict]:
    """
    Rerank candidates by score (descending).
    Return top RERANK_FINAL_K (6) chunks.
    Works for both vector similarity scores and BM25 rank scores.
    """
    sorted_candidates = sorted(candidates, key=lambda c: c.get("score", 0), reverse=True)
    return sorted_candidates[:RERANK_FINAL_K]


# ─── Weak Match Detection ─────────────────────────────────────────────────────

def _is_weak_match(reranked: list[dict], confidence: str) -> bool:
    """
    Determine if the match is too weak to generate a reliable answer.
    Returns True if:
    - confidence == "low"
    - OR max score among reranked chunks < WEAK_MATCH_SCORE_THRESHOLD (0.50)
    
    For fulltext search, BM25 scores are typically much lower than cosine similarity,
    so we use a different threshold.
    """
    if confidence == "low":
        return True
    if not reranked:
        return True
    if EMBEDDING_PROVIDER == "openai":
        max_score = max(c.get("score", 0) for c in reranked)
        if max_score < WEAK_MATCH_SCORE_THRESHOLD:
            return True
    # For fulltext: if we have results, they matched the query — trust them
    # Confidence is still determined by score distribution
    return False


# ─── Context Building ─────────────────────────────────────────────────────────

def _build_context(chunks: list[dict]) -> str:
    """Build the context string from the reranked chunks for the LLM prompt."""
    parts = []
    for i, chunk in enumerate(chunks, 1):
        page_info = ""
        if chunk.get("page_start"):
            page_info = f", sida {chunk['page_start']}"
            if chunk.get("page_end") and chunk["page_end"] != chunk["page_start"]:
                page_info += f"-{chunk['page_end']}"
        parts.append(
            f"[{i}] {chunk['document_title']} "
            f"(v{chunk.get('document_version', '?')}{page_info})\n"
            f"Chunk ID: {chunk['chunk_id']}\n"
            f"{chunk['content']}"
        )
    return "\n\n---\n\n".join(parts)


def _determine_confidence(chunks: list[dict]) -> str:
    """
    Determine confidence level based on average score.
    For vector search: cosine similarity thresholds.
    For fulltext: BM25 score thresholds (different scale).
    """
    if not chunks:
        return "low"
    avg_score = sum(c.get("score", 0) for c in chunks) / len(chunks)
    if EMBEDDING_PROVIDER == "fulltext":
        # BM25 scores are typically 0.0-1.0 but much lower than cosine
        if avg_score >= 0.1:
            return "high"
        elif avg_score >= 0.01:
            return "medium"
        return "low"
    else:
        if avg_score >= 0.75:
            return "high"
        elif avg_score >= 0.50:
            return "medium"
        return "low"


# ─── Logging ──────────────────────────────────────────────────────────────────

def _log_query(
    query_id: str,
    user_id: str | None,
    collection_id: str,
    mode: str,
    question: str,
    answer: str,
    citations: list[CitationItem],
    confidence: str,
    latency_ms: int,
    reranked_chunks: list[dict],
) -> None:
    """
    Best-effort logging of query and retrieved chunks to the database.
    Uses admin client for insert (user may not have INSERT on knowledge_queries via RLS).
    If logging fails, the query endpoint still returns the answer — logging never crashes the user.
    """
    try:
        admin = get_admin_supabase()

        # Insert query record
        admin.table("knowledge_queries").insert({
            "id": query_id,
            "user_id": user_id,
            "collection_id": collection_id,
            "mode": mode,
            "question": question,
            "answer": answer,
            "answer_citations": [c.model_dump(mode="json") for c in citations],
            "confidence": confidence,
            "latency_ms": latency_ms,
        }).execute()

        # Insert query-chunk associations
        if reranked_chunks:
            chunk_rows = [
                {
                    "query_id": query_id,
                    "chunk_id": str(c["chunk_id"]),
                    "rank": i + 1,
                    "score": c.get("score", 0),
                }
                for i, c in enumerate(reranked_chunks)
            ]
            admin.table("knowledge_query_chunks").insert(chunk_rows).execute()
    except Exception:
        logger.warning("Best-effort query logging failed for query_id=%s", query_id)


# ─── Main Query Pipeline ──────────────────────────────────────────────────────

async def process_query(
    question: str,
    collection_id: str,
    mode: str,
    jwt: str,
) -> QueryResponse:
    """
    Full RAG pipeline:
    1. Extract user_id from JWT sub claim (for logging only)
    2. Retrieve 30 candidates (user JWT, RLS enforced) — vector or fulltext
    3. Rerank to top 6
    4. Weak match check: confidence == "low" OR max(score) < threshold → "ospecificerat i underlaget"
    5. Build context and generate answer via LLM
    6. Log query + chunk associations (admin client, best-effort)
    7. Return structured response with citations
    """
    start_time = time.time()
    query_id = str(uuid4())

    # 1. Extract user_id from JWT for logging (not for access control)
    user_id = extract_user_id_from_jwt(jwt)

    # 2. Retrieve candidates
    candidates = await _retrieve_candidates(question, collection_id, jwt)

    # 3. Rerank
    reranked = _rerank(candidates)

    # 4. Determine confidence
    confidence = _determine_confidence(reranked)

    # 5. Weak match check — before building context or calling LLM
    if not reranked or _is_weak_match(reranked, confidence):
        answer = NO_ANSWER
        citations: list[CitationItem] = []
        retrieved_chunks: list[RetrievedChunk] = []
    else:
        # Build context and generate answer
        context = _build_context(reranked)
        mode_instruction = MODE_INSTRUCTIONS.get(mode, MODE_INSTRUCTIONS["technical"])
        system_prompt = SYSTEM_PROMPT_TEMPLATE.format(
            mode_instruction=mode_instruction,
            context=context,
        )
        answer = await chat_completion(system_prompt, question)

        # Build citations
        citations = [
            CitationItem(
                chunk_id=c["chunk_id"],
                document_id=c["document_id"],
                document_title=c["document_title"],
                document_version=c.get("document_version"),
                page_start=c.get("page_start"),
                page_end=c.get("page_end"),
                section=c.get("section"),
                content_preview=c["content"][:300],
            )
            for c in reranked
        ]

        # Build retrieved chunks for full transparency
        retrieved_chunks = [
            RetrievedChunk(
                chunk_id=c["chunk_id"],
                document_id=c["document_id"],
                document_title=c["document_title"],
                content=c["content"],
                score=c.get("score", 0),
                rank=i + 1,
                page_start=c.get("page_start"),
                page_end=c.get("page_end"),
                section=c.get("section"),
            )
            for i, c in enumerate(reranked)
        ]

    latency_ms = int((time.time() - start_time) * 1000)

    # 6. Log everything
    _log_query(
        query_id=query_id,
        user_id=user_id,
        collection_id=collection_id,
        mode=mode,
        question=question,
        answer=answer,
        citations=citations,
        confidence=confidence,
        latency_ms=latency_ms,
        reranked_chunks=reranked,
    )

    return QueryResponse(
        query_id=UUID(query_id),
        answer=answer,
        citations=citations,
        retrieved_chunks=retrieved_chunks,
        confidence=confidence,
        latency_ms=latency_ms,
    )
