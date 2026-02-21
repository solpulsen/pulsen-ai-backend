"""
Documents router — /api/v1/knowledge/documents

Admin-facing endpoints. Uses service_role key via get_admin_supabase().
These endpoints are for document upload, listing, activation, and archival.
In production, protect with admin-only middleware or API key.
"""
from __future__ import annotations
import hashlib
import uuid
from typing import Optional

from fastapi import APIRouter, File, Form, HTTPException, UploadFile, status

from knowledge_engine.core.supabase_client import get_admin_supabase
from knowledge_engine.models.schemas import DocumentResponse, DocumentListResponse
from knowledge_engine.services.ingestion import ingest_document

router = APIRouter(prefix="/documents", tags=["Documents"])


@router.post("", status_code=status.HTTP_201_CREATED, response_model=DocumentResponse)
async def upload_document(
    file: UploadFile = File(...),
    title: str = Form(...),
    category: str = Form(...),
    version: str = Form("v1.0"),
    language: str = Form("sv"),
    source: Optional[str] = Form(None),
    product_family: Optional[str] = Form(None),
    collection_ids: Optional[str] = Form(None),  # Comma-separated UUIDs
):
    """Upload a document and trigger ingestion pipeline."""
    supabase = get_admin_supabase()
    file_bytes = await file.read()
    checksum = hashlib.sha256(file_bytes).hexdigest()

    # Upload file to Supabase Storage
    storage_path = f"knowledge/{uuid.uuid4()}/{file.filename}"
    supabase.storage.from_("knowledge-documents").upload(
        storage_path, file_bytes, {"content-type": file.content_type or "application/octet-stream"}
    )

    # Create document record with status=draft
    canonical_id = str(uuid.uuid4())
    doc_data = {
        "canonical_id": canonical_id,
        "version_num": 1,
        "is_latest": True,
        "title": title,
        "source": source,
        "category": category,
        "product_family": product_family,
        "version": version,
        "language": language,
        "status": "draft",
        "storage_path": storage_path,
        "checksum": checksum,
    }
    result = supabase.table("knowledge_documents").insert(doc_data).execute()
    if not result.data:
        raise HTTPException(status_code=500, detail="Failed to create document record")

    document = result.data[0]
    document_id = document["id"]

    # Link to collections if provided
    if collection_ids:
        for cid in collection_ids.split(","):
            cid = cid.strip()
            if cid:
                supabase.table("knowledge_collection_documents").insert({
                    "collection_id": cid,
                    "document_id": document_id,
                }).execute()

    # Run ingestion pipeline asynchronously
    await ingest_document(document_id, file_bytes, file.filename or "document")

    return DocumentResponse(**document)


@router.get("", response_model=DocumentListResponse)
async def list_documents(
    category: Optional[str] = None,
    status_filter: Optional[str] = None,
    collection_id: Optional[str] = None,
):
    """List documents with optional filters."""
    supabase = get_admin_supabase()
    query = supabase.table("knowledge_documents").select("*")
    if category:
        query = query.eq("category", category)
    if status_filter:
        query = query.eq("status", status_filter)
    result = query.execute()
    docs = result.data or []
    return DocumentListResponse(documents=[DocumentResponse(**d) for d in docs], total=len(docs))


@router.get("/{document_id}", response_model=DocumentResponse)
async def get_document(document_id: str):
    supabase = get_admin_supabase()
    result = supabase.table("knowledge_documents").select("*").eq("id", document_id).single().execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="Document not found")
    return DocumentResponse(**result.data)


@router.post("/{document_id}/activate", response_model=DocumentResponse)
async def activate_document(document_id: str):
    """Activate a document, making it searchable."""
    supabase = get_admin_supabase()
    result = supabase.table("knowledge_documents").update({"status": "active"}).eq("id", document_id).execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="Document not found")
    return DocumentResponse(**result.data[0])


@router.post("/{document_id}/archive", response_model=DocumentResponse)
async def archive_document(document_id: str):
    """Archive a document, removing it from search."""
    supabase = get_admin_supabase()
    result = supabase.table("knowledge_documents").update({"status": "archived"}).eq("id", document_id).execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="Document not found")
    return DocumentResponse(**result.data[0])
