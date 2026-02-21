"""
Collections router — /api/v1/knowledge/collections

User-facing endpoints. All requests use the user's Supabase JWT via
get_bearer_token dependency. RLS is fully enforced. service_role is NEVER used.
"""
from __future__ import annotations
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status

from knowledge_engine.dependencies.auth import get_bearer_token
from knowledge_engine.core.supabase_client import get_user_supabase
from knowledge_engine.models.schemas import CollectionCreate, CollectionResponse

router = APIRouter(prefix="/collections", tags=["Collections"])


@router.get("", response_model=list[CollectionResponse])
async def list_collections(jwt: str = Depends(get_bearer_token)):
    """
    List all collections the authenticated user has access to.
    RLS ensures only assigned or default collections are returned.
    """
    client = get_user_supabase(jwt)
    result = client.table("knowledge_collections").select("*").order("created_at").execute()
    return [CollectionResponse(**c) for c in (result.data or [])]


@router.get("/{collection_id}", response_model=CollectionResponse)
async def get_collection(collection_id: str, jwt: str = Depends(get_bearer_token)):
    """Get a single collection by ID. RLS enforced."""
    client = get_user_supabase(jwt)
    result = client.table("knowledge_collections").select("*").eq("id", collection_id).single().execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="Collection not found")
    return CollectionResponse(**result.data)


@router.get("/{collection_id}/documents")
async def list_collection_documents(collection_id: str, jwt: str = Depends(get_bearer_token)):
    """
    List all documents in a collection.
    RLS on knowledge_collection_documents + knowledge_documents ensures
    only active documents in accessible collections are returned.
    """
    client = get_user_supabase(jwt)

    # Get document IDs linked to this collection
    links = client.table("knowledge_collection_documents") \
        .select("document_id") \
        .eq("collection_id", collection_id) \
        .execute()

    if not links.data:
        return {"documents": [], "total": 0}

    doc_ids = [link["document_id"] for link in links.data]

    # Fetch the actual documents (RLS filters to active + accessible)
    docs = client.table("knowledge_documents") \
        .select("*") \
        .in_("id", doc_ids) \
        .order("created_at") \
        .execute()

    return {"documents": docs.data or [], "total": len(docs.data or [])}
