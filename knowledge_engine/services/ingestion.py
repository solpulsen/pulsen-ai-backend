"""
Ingestion service.
Handles text extraction, chunking, optional embedding, and storage of documents.

When EMBEDDING_PROVIDER=fulltext, chunks are stored without embeddings.
The tsvector column is auto-populated by the DB trigger (migration 004).
When EMBEDDING_PROVIDER=openai, chunks are embedded via text-embedding-3-small.
"""
from __future__ import annotations
import hashlib
import io
import logging
import re
from typing import Optional

import tiktoken
from PyPDF2 import PdfReader
from docx import Document as DocxDocument

from knowledge_engine.core.config import (
    CHUNK_TARGET_TOKENS,
    CHUNK_OVERLAP_TOKENS,
    CHUNK_MAX_TOKENS,
    EMBEDDING_PROVIDER,
)
from knowledge_engine.core.supabase_client import get_admin_supabase

logger = logging.getLogger(__name__)

_tokenizer = tiktoken.encoding_for_model("gpt-4o")


# ─── Text Extraction ──────────────────────────────────────────────────────────

def extract_text_from_pdf(file_bytes: bytes) -> list[dict]:
    """Extract text from PDF, preserving page numbers."""
    reader = PdfReader(io.BytesIO(file_bytes))
    pages = []
    for i, page in enumerate(reader.pages):
        text = page.extract_text() or ""
        if text.strip():
            pages.append({"page": i + 1, "text": text})
    return pages


def extract_text_from_docx(file_bytes: bytes) -> str:
    """Extract text from DOCX file."""
    doc = DocxDocument(io.BytesIO(file_bytes))
    return "\n".join(para.text for para in doc.paragraphs if para.text.strip())


def extract_text(file_bytes: bytes, filename: str) -> tuple[str, list[dict]]:
    """
    Extract text from a file based on its extension.
    Returns (full_text, page_map) where page_map is a list of {page, text} dicts.
    """
    ext = filename.lower().rsplit(".", 1)[-1]
    if ext == "pdf":
        pages = extract_text_from_pdf(file_bytes)
        full_text = "\n".join(p["text"] for p in pages)
        return full_text, pages
    elif ext in ("docx", "doc"):
        text = extract_text_from_docx(file_bytes)
        return text, [{"page": 1, "text": text}]
    elif ext in ("md", "txt", "html"):
        text = file_bytes.decode("utf-8", errors="replace")
        if ext == "html":
            text = re.sub(r"<[^>]+>", " ", text)
        return text, [{"page": 1, "text": text}]
    else:
        raise ValueError(f"Unsupported file type: {ext}")


# ─── Chunking ─────────────────────────────────────────────────────────────────

def _count_tokens(text: str) -> int:
    return len(_tokenizer.encode(text))


def _split_into_chunks(text: str, page_map: list[dict]) -> list[dict]:
    """
    Split text into overlapping chunks of ~CHUNK_TARGET_TOKENS tokens.
    Preserves page number context from the page_map.
    """
    sentences: list[tuple[str, int]] = []
    for page_info in page_map:
        page_num = page_info["page"]
        for sent in re.split(r"(?<=[.!?])\s+", page_info["text"]):
            sent = sent.strip()
            if sent:
                sentences.append((sent, page_num))

    chunks = []
    current_tokens = 0
    current_sentences: list[tuple[str, int]] = []
    chunk_index = 0

    for sent, page_num in sentences:
        sent_tokens = _count_tokens(sent)

        if current_tokens + sent_tokens > CHUNK_MAX_TOKENS and current_sentences:
            chunk_text = " ".join(s for s, _ in current_sentences)
            pages = [p for _, p in current_sentences]
            chunks.append({
                "chunk_index": chunk_index,
                "content": chunk_text,
                "content_tokens": current_tokens,
                "page_start": min(pages),
                "page_end": max(pages),
            })
            chunk_index += 1

            overlap_sentences = []
            overlap_tokens = 0
            for s, p in reversed(current_sentences):
                t = _count_tokens(s)
                if overlap_tokens + t <= CHUNK_OVERLAP_TOKENS:
                    overlap_sentences.insert(0, (s, p))
                    overlap_tokens += t
                else:
                    break
            current_sentences = overlap_sentences
            current_tokens = overlap_tokens

        current_sentences.append((sent, page_num))
        current_tokens += sent_tokens

    if current_sentences:
        chunk_text = " ".join(s for s, _ in current_sentences)
        pages = [p for _, p in current_sentences]
        chunks.append({
            "chunk_index": chunk_index,
            "content": chunk_text,
            "content_tokens": current_tokens,
            "page_start": min(pages),
            "page_end": max(pages),
        })

    return chunks


# ─── Embedding with Deduplication ─────────────────────────────────────────────

async def _get_or_create_embedding(content: str, content_hash: str) -> list[float] | None:
    """
    Check embeddings_cache first. If found, return cached embedding.
    Otherwise, generate via OpenAI, cache it, and return.
    Returns None if EMBEDDING_PROVIDER is not openai.
    """
    if EMBEDDING_PROVIDER != "openai":
        return None

    from knowledge_engine.core.embeddings import get_embedder

    supabase = get_admin_supabase()

    # Check cache
    result = supabase.table("embeddings_cache").select("embedding").eq("content_hash", content_hash).execute()
    if result.data:
        return result.data[0]["embedding"]

    # Generate new embedding
    embedder = get_embedder()
    embedding = await embedder.embed_query(content)
    token_count = _count_tokens(content)

    # Store in cache
    supabase.table("embeddings_cache").insert({
        "content_hash": content_hash,
        "embedding": embedding,
        "tokens": token_count,
        "model_version": embedder.model_name,
    }).execute()

    return embedding


# ─── Main Ingestion Pipeline ──────────────────────────────────────────────────

async def ingest_document(document_id: str, file_bytes: bytes, filename: str) -> int:
    """
    Full ingestion pipeline for a document:
    1. Extract text
    2. Chunk text
    3. Optionally embed each chunk (with deduplication)
    4. Store chunks in knowledge_chunks table
    
    When EMBEDDING_PROVIDER=fulltext, chunks are stored without embeddings.
    The DB trigger (migration 004) auto-populates the tsvector column.
    
    Returns the number of chunks created.
    """
    supabase = get_admin_supabase()

    # 1. Extract text
    full_text, page_map = extract_text(file_bytes, filename)

    # 2. Chunk
    chunks = _split_into_chunks(full_text, page_map)

    # 3 & 4. Embed (if applicable) and store
    rows = []
    for chunk in chunks:
        content = chunk["content"]
        content_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()

        embedding = await _get_or_create_embedding(content, content_hash)

        row = {
            "document_id": document_id,
            "chunk_index": chunk["chunk_index"],
            "content": content,
            "content_hash": content_hash,
            "content_tokens": chunk["content_tokens"],
            "page_start": chunk.get("page_start"),
            "page_end": chunk.get("page_end"),
        }
        if embedding is not None:
            row["embedding"] = embedding

        rows.append(row)

    if rows:
        supabase.table("knowledge_chunks").insert(rows).execute()

    logger.info(
        "Ingested %d chunks for document %s (embeddings: %s)",
        len(rows), document_id, EMBEDDING_PROVIDER == "openai",
    )
    return len(rows)
