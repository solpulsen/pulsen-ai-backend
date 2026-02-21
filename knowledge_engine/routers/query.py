"""
Query router — /api/v1/knowledge/query

User-facing endpoint. Uses the user's Supabase JWT via get_bearer_token dependency.
RLS is enforced for retrieval. service_role is NEVER used for user queries.
Admin client is used ONLY for logging (insert into knowledge_queries/knowledge_query_chunks).
user_id is extracted from JWT sub claim inside the service (for logging only).
"""
from __future__ import annotations

from fastapi import APIRouter, Depends

from knowledge_engine.dependencies.auth import get_bearer_token
from knowledge_engine.models.schemas import QueryRequest, QueryResponse
from knowledge_engine.services.query import process_query

router = APIRouter(prefix="/query", tags=["Query"])


@router.post("", response_model=QueryResponse)
async def query_knowledge(
    request: QueryRequest,
    jwt: str = Depends(get_bearer_token),
):
    """
    RAG query pipeline:
    1. Extract user_id from JWT sub claim (logging only)
    2. Embed question with text-embedding-3-small
    3. Vector search top_k=30 in knowledge_chunks (user JWT, RLS enforced)
    4. Rerank to top 6
    5. Weak match check: confidence == "low" OR max(score) < 0.50 → "ospecificerat i underlaget"
    6. Generate answer with citations (doc_id + chunk_id)
    7. Log in knowledge_queries + knowledge_query_chunks
    """
    response = await process_query(
        question=request.question,
        collection_id=str(request.collection_id),
        mode=request.mode,
        jwt=jwt,
    )
    return response
