# Database Migrations — Pulsen A.I. Knowledge Engine

All database schema changes are defined in numbered SQL scripts. Execute them in order against the Supabase PostgreSQL database.

## Migration Order

| Order | Script | Description |
| :--- | :--- | :--- |
| 1 | `001_initial_schema.sql` | Core schema: 10 tables, VECTOR(1536) columns, HNSW indexes, versioning, embeddings_cache |
| 2 | `002_rls_and_roles.sql` | Row-Level Security policies, user roles (app_role enum), collection-based ACL |
| 3 | `003_rpc_match_knowledge_chunks.sql` | RPC function for vector similarity search (cosine distance), SECURITY INVOKER |
| 4 | `004_fulltext_search_fallback.sql` | Fulltext search fallback: tsvector column, GIN index, trigger, BM25 RPC function |

## Security Measures

1. **RLS from the start**: Enabled on all data tables before any application logic.
2. **Collection-based ACL**: Users can only access documents in their assigned collections.
3. **Embedding deduplication**: `embeddings_cache` table prevents redundant API calls.
4. **Backend-only service_role**: Never exposed to frontend; only used for admin flows.
5. **SECURITY INVOKER**: All RPC functions run as the calling user, enforcing RLS.
6. **Fixed search_path**: All SECURITY DEFINER functions use `SET search_path = public`.

## Embedding Provider

The system supports two retrieval methods:

- **openai**: Vector search via `text-embedding-3-small` (1536 dims) + `match_knowledge_chunks` RPC
- **fulltext**: Postgres BM25 fulltext search via `search_knowledge_chunks_fulltext` RPC (no API key needed)

Set `EMBEDDING_PROVIDER=fulltext` or `EMBEDDING_PROVIDER=openai` in your environment.
