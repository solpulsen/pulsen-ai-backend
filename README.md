# Pulsen A.I. Knowledge Engine — Backend

Internal RAG (Retrieval-Augmented Generation) system for Solpulsen Energy Hub. Provides document management, semantic search, and LLM-powered Q&A with citations.

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
| `EMBEDDING_PROVIDER` | No | `openai` or `fulltext` (default: `openai`) |
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
