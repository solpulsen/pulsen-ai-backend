-- Migration 004: Fulltext Search Fallback
-- Adds tsvector column and GIN index on knowledge_chunks for BM25-style text search.
-- Creates an RPC function for fulltext retrieval that respects RLS (SECURITY INVOKER).
-- This is used when embedding provider is unavailable (e.g., no OpenAI API key).

-- 1. Add tsvector column for fulltext search
ALTER TABLE knowledge_chunks
ADD COLUMN IF NOT EXISTS tsv tsvector;

-- 2. Populate tsvector from content (Swedish + English config)
UPDATE knowledge_chunks
SET tsv = to_tsvector('swedish', coalesce(content, ''));

-- 3. Create GIN index for fast fulltext search
CREATE INDEX IF NOT EXISTS idx_chunks_tsv ON knowledge_chunks USING GIN (tsv);

-- 4. Create trigger to auto-update tsvector on insert/update
CREATE OR REPLACE FUNCTION update_chunks_tsv()
RETURNS trigger AS $$
BEGIN
    NEW.tsv := to_tsvector('swedish', coalesce(NEW.content, ''));
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_chunks_tsv ON knowledge_chunks;
CREATE TRIGGER trg_chunks_tsv
    BEFORE INSERT OR UPDATE OF content ON knowledge_chunks
    FOR EACH ROW
    EXECUTE FUNCTION update_chunks_tsv();

-- 5. RPC function for fulltext search — SECURITY INVOKER (RLS enforced)
CREATE OR REPLACE FUNCTION public.search_knowledge_chunks_fulltext(
    search_query text,
    collection_id_filter uuid,
    match_count int default 30
)
RETURNS TABLE (
    chunk_id uuid,
    document_id uuid,
    document_title text,
    document_version text,
    content text,
    page_start int,
    page_end int,
    section text,
    score float
)
LANGUAGE sql
SECURITY INVOKER
SET search_path = public
AS $$
    SELECT
        kc.id AS chunk_id,
        kd.id AS document_id,
        kd.title AS document_title,
        kd.version_num::text AS document_version,
        kc.content AS content,
        kc.page_start,
        kc.page_end,
        kc.section,
        ts_rank_cd(kc.tsv, plainto_tsquery('swedish', search_query))::float AS score
    FROM knowledge_chunks kc
    JOIN knowledge_documents kd ON kd.id = kc.document_id
    JOIN knowledge_collection_documents kcd ON kcd.document_id = kd.id
    WHERE kd.status = 'active'
      AND kcd.collection_id = collection_id_filter
      AND kc.tsv @@ plainto_tsquery('swedish', search_query)
    ORDER BY ts_rank_cd(kc.tsv, plainto_tsquery('swedish', search_query)) DESC
    LIMIT match_count;
$$;
