# Pulsen A.I. Knowledge Engine — Frozen Architecture

**Status**: LOCKED. No changes without migration + full reindex + team approval.
**Date**: 2026-02-22

## Locked Decisions

| Component | Decision | Rationale |
| :--- | :--- | :--- |
| Embedding model | `text-embedding-3-small` | Best cost/quality ratio for Swedish technical docs |
| Embedding dimensions | `1536` | Matches DB schema `VECTOR(1536)` and HNSW index |
| Vector index | HNSW with `vector_cosine_ops` | Production-proven, tunable via `ef_search` |
| Fulltext fallback | Postgres tsvector + `ts_rank_cd` | Swedish config, BM25-style, zero API cost |
| Chat model | `gpt-4.1-mini` | Fast, accurate, cost-effective for RAG answers |
| Chunk size | ~1000 tokens (max 1200, overlap 125) | Optimal for citation granularity |
| Database | Supabase PostgreSQL 17 + pgvector | RLS, RPC, managed infrastructure |
| Auth | Supabase JWT + RLS | Collection-based ACL, SECURITY INVOKER on all RPCs |

## What Changing These Requires

Changing the embedding model or dimensions requires:

1. A new migration to alter `VECTOR(N)` column type
2. Dropping and recreating the HNSW index
3. Re-embedding ALL existing chunks (full reindex)
4. Updating `embeddings_cache` table
5. Updating `config.py` frozen constants
6. Full regression test of query pipeline

**This is a multi-hour operation with downtime. Do not do it casually.**

## Schema Overview

```
knowledge_collections
  └── knowledge_collection_documents (junction)
        └── knowledge_documents
              └── knowledge_chunks (VECTOR(1536), tsvector, HNSW index)

knowledge_queries (audit log)
  └── knowledge_query_chunks (chunk-level audit)

knowledge_feedback (user ratings)

embeddings_cache (deduplication by content_hash)
```

## Security Model

All RPC functions use `SECURITY INVOKER` — they run as the calling user, enforcing RLS policies. The `service_role` key is used exclusively in the backend for admin operations (document upload, ingestion, activation). It is never exposed to the frontend, never logged, and never hardcoded.

## Retrieval Pipeline

```
User question
  → Embed query (if openai) or parse to tsquery (if fulltext)
  → RPC call (match_knowledge_chunks or search_knowledge_chunks_fulltext)
  → RLS filters results by user's collection access
  → Top-K chunks returned (default: 6, score threshold: 0.30)
  → LLM generates answer with citations
  → Response includes: answer, citations[], retrieved_chunks[], confidence, query_id
  → Query + chunks logged to knowledge_queries + knowledge_query_chunks
```

## File Structure

```
knowledge_engine/
├── core/
│   ├── config.py          # Frozen constants + env loading
│   ├── embeddings.py      # Locked embedding provider
│   ├── openai_client.py   # Chat completion wrapper
│   └── supabase_client.py # Admin + user client factories
├── dependencies/
│   └── auth.py            # JWT extraction + validation
├── models/
│   └── schemas.py         # Pydantic request/response models
├── routers/
│   ├── query.py           # POST /api/v1/knowledge/query
│   ├── collections.py     # GET collections
│   ├── documents.py       # Admin document management
│   └── feedback.py        # POST feedback
├── services/
│   ├── query.py           # RAG pipeline orchestration
│   └── ingestion.py       # PDF/DOCX → chunks → storage
├── tests/
│   └── e2e_demo.py        # End-to-end demo (env-only secrets)
└── main.py                # FastAPI app entry point
```
