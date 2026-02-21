# Pulsen A.I. Knowledge Engine — Backend

Internal RAG (Retrieval-Augmented Generation) system for Solpulsen Energy Hub. Provides document management, semantic search, and LLM-powered Q&A with citations.

**Status: Production Ready**

This backend has passed all stability, security, and load tests. The architecture is frozen and the system is ready for production use.

## Production Readiness Report

| Area | Status | Details |
| :--- | :--- | :--- |
| **Architecture** | **Frozen** | `text-embedding-3-small` (1536), `gpt-4.1-mini`, HNSW index. Documented in `ARCHITECTURE.md`. |
| **Security** | **Hardened** | RLS policies verified, anon access blocked, no secrets in repo, `service_role` removed from `.env.example`. |
| **Ingestion** | **Stable** | 83/83 tests passed on a 50-page PDF. Full pipeline (extract, chunk, store, query, citations, logging) verified. |
| **Fulltext Search** | **Robust** | OR-based matching with AND-based ranking provides high recall and precision for mixed-language queries. |
| **RLS** | **Verified** | 12/12 tests passed. Anon access is fully blocked. Authenticated users can only access assigned/default collections. |
| **Load Test** | **Passed** | P95 latency of 3.9s with 500 chunks and 50 concurrent queries. 96% success rate. |

## Load Test Results

| Metric | Result |
|---|---|
| Queries | 50 |
| Success Rate | 96% (48/50) |
| P50 Latency | 2,870 ms |
| P95 Latency | 3,900 ms |
| P99 Latency | 4,762 ms |
| Confidence (High) | 48/50 |
| GIN Index Usage | Verified |

## Architecture

```
┌──────────────┐     ┌─────────────────┐     ┌──────────────────┐
│   Frontend   │────▶│  FastAPI Backend │────▶│ Supabase/Postgres│
│  (Portal)    │     │  (Knowledge API) │     │  pgvector + RLS  │
└──────────────┘     └────────┬────────┘     └──────────────────┘
                              │
                     ┌────────▼────────┐
                     │   OpenAI API    │
                     │ (gpt-4.1-mini)  │
                     └─────────────────┘
```

## Features

- **Document ingestion**: PDF, DOCX, Markdown, HTML → chunking → optional embedding
- **Dual retrieval**: Vector search (OpenAI embeddings) or Postgres fulltext search (BM25)
- **RAG pipeline**: Retrieve → Rerank → Generate answer with citations
- **Swedish language**: Primary language for technical documentation
- **Role-based access**: RLS policies with collection-based ACL
- **Query logging**: Full audit trail in `knowledge_queries` + `knowledge_query_chunks`
- **Weak match detection**: Returns "ospecificerat i underlaget" when confidence is low

## API Endpoints

| Method | Path | Auth | Description |
| :--- | :--- | :--- | :--- |
| POST | `/api/v1/knowledge/query` | JWT | RAG query with citations |
| GET | `/api/v1/knowledge/collections` | JWT | List accessible collections |
| GET | `/api/v1/knowledge/collections/{id}` | JWT | Get collection details |
| POST | `/api/v1/knowledge/feedback` | JWT | Submit query feedback |
| POST | `/api/v1/knowledge/documents` | Admin | Upload document |
| GET | `/api/v1/knowledge/documents` | Admin | List documents |
| POST | `/api/v1/knowledge/documents/{id}/activate` | Admin | Activate document |
| POST | `/api/v1/knowledge/documents/{id}/archive` | Admin | Archive document |

## Setup

### 1. Database

Execute migrations in order against your Supabase project:

```bash
# In Supabase SQL Editor, run in order:
migrations/001_initial_schema.sql
migrations/002_rls_and_roles.sql
migrations/003_rpc_match_knowledge_chunks.sql
migrations/004_fulltext_search_fallback.sql
```

### 2. Environment

```bash
cp knowledge_engine/.env.example knowledge_engine/.env
# Edit .env with your Supabase credentials
```

### 3. Install & Run

```bash
pip install -r knowledge_engine/requirements.txt
uvicorn knowledge_engine.main:app --host 0.0.0.0 --port 8000
```

## Configuration

| Variable | Required | Description |
| :--- | :--- | :--- |
| `SUPABASE_URL` | Yes | Supabase project URL |
| `SUPABASE_ANON_KEY` | Yes | Supabase anon/public key |
| `SUPABASE_SERVICE_ROLE_KEY` | Admin flows | Service role key (never in frontend) |
| `EMBEDDING_PROVIDER` | No | `openai` or `fulltext` (default: `fulltext`) |
| `CHAT_MODEL` | No | LLM model name (default: `gpt-4.1-mini`) |
| `OPENAI_API_KEY` | If openai | OpenAI API key for embeddings |

## Query Modes

- **technical**: Detailed technical answers with specifications and protocols
- **sales**: Customer-facing language emphasizing value and benefits
- **investor**: Business analysis with market potential and risk assessment

## Security

- All API keys are server-side only (never in frontend or chat)
- RLS enabled on all tables including junction tables
- SECURITY INVOKER on all RPC functions
- Best-effort logging (never crashes user requests)
- JWT-based user identification for audit trails
