"""
Feedback router — /api/v1/knowledge/feedback

User-facing endpoint. Uses the user's Supabase JWT via get_bearer_token dependency.
RLS is enforced. service_role is NEVER used.

Feedback is limited to INSERT + SELECT in v1 (no DELETE/UPDATE for users).
RLS policy on knowledge_feedback requires that the query belongs to the user:
  EXISTS(SELECT 1 FROM knowledge_queries WHERE id=query_id AND user_id=auth.uid())
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from knowledge_engine.dependencies.auth import get_bearer_token
from knowledge_engine.core.supabase_client import get_user_supabase
from knowledge_engine.models.schemas import FeedbackCreate, FeedbackResponse

router = APIRouter(prefix="/feedback", tags=["Feedback"])


@router.post("", status_code=status.HTTP_201_CREATED, response_model=FeedbackResponse)
async def submit_feedback(
    request: FeedbackCreate,
    jwt: str = Depends(get_bearer_token),
):
    """
    Submit feedback for a query.
    RLS ensures the user can only submit feedback for their own queries.
    Rating must be 1-5 (enforced by Pydantic schema + DB CHECK constraint).
    """
    client = get_user_supabase(jwt)

    # Insert feedback — RLS policy will reject if query doesn't belong to user
    result = client.table("knowledge_feedback").insert({
        "query_id": str(request.query_id),
        "rating": request.rating,
        "issue_type": request.issue_type,
        "comment": request.comment,
    }).execute()

    if not result.data:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot submit feedback: query not found or not owned by you",
        )

    return FeedbackResponse(**result.data[0])


@router.get("", response_model=list[FeedbackResponse])
async def list_my_feedback(jwt: str = Depends(get_bearer_token)):
    """
    List all feedback submitted by the authenticated user.
    RLS ensures only the user's own feedback is returned.
    """
    client = get_user_supabase(jwt)
    result = client.table("knowledge_feedback").select("*").order("created_at", desc=True).execute()
    return [FeedbackResponse(**f) for f in (result.data or [])]
