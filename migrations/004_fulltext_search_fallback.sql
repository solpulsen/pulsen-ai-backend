-- Migration 004: Fulltext Search Fallback (v3 — OR-based recall)
-- Adds tsvector column and GIN index on knowledge_chunks for BM25-style text search.
-- Creates an RPC function for fulltext retrieval that respects RLS (SECURITY INVOKER).
--
-- Key design decisions:
-- 1. Dual-config tsvector (swedish + simple) for mixed-language content
-- 2. OR-based query matching for high recall (AND is too strict for natural language)
-- 3. ts_rank_cd scoring uses the AND query for precision ranking
-- 4. Matching uses OR query so partial term overlap still returns results

-- 1. Add tsvector column for fulltext search
ALTER TABLE knowledge_chunks
ADD COLUMN IF NOT EXISTS tsv tsvector;

-- 2. Populate tsvector from content (Swedish + Simple for mixed-language support)
UPDATE knowledge_chunks
SET tsv = to_tsvector('swedish', coalesce(content, ''))
       || to_tsvector('simple', coalesce(content, ''));

-- 3. Create GIN index for fast fulltext search
CREATE INDEX IF NOT EXISTS idx_chunks_tsv ON knowledge_chunks USING GIN (tsv);

-- 4. Create trigger to auto-update tsvector on insert/update
CREATE OR REPLACE FUNCTION update_chunks_tsv()
RETURNS trigger AS $$
BEGIN
    NEW.tsv := to_tsvector('swedish', coalesce(NEW.content, ''))
            || to_tsvector('simple', coalesce(NEW.content, ''));
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_chunks_tsv ON knowledge_chunks;
CREATE TRIGGER trg_chunks_tsv
    BEFORE INSERT OR UPDATE OF content ON knowledge_chunks
    FOR EACH ROW
    EXECUTE FUNCTION update_chunks_tsv();

-- 5. Helper: convert a plain text query into an OR-based tsquery
-- "peak shaving EMS" → 'peak' | 'shaving' | 'ems' (simple config)
-- This gives high recall; ranking by ts_rank_cd handles precision.
CREATE OR REPLACE FUNCTION build_or_tsquery(config regconfig, query_text text)
RETURNS tsquery AS $$
DECLARE
    words text[];
    word text;
    result tsquery;
    term tsquery;
BEGIN
    -- Split on whitespace and punctuation, remove empty strings
    words := regexp_split_to_array(lower(trim(query_text)), '[^a-zåäöA-ZÅÄÖ0-9]+');
    result := NULL;
    FOREACH word IN ARRAY words LOOP
        IF length(word) > 1 THEN  -- skip single chars
            term := to_tsquery(config, word);
            IF result IS NULL THEN
                result := term;
            ELSE
                result := result || term;  -- || = OR for tsquery
            END IF;
        END IF;
    END LOOP;
    RETURN coalesce(result, plainto_tsquery(config, query_text));
END;
$$ LANGUAGE plpgsql IMMUTABLE;

-- 6. RPC function for fulltext search — SECURITY INVOKER (RLS enforced)
-- Uses OR-based matching for recall, AND-based ranking for precision.
DROP FUNCTION IF EXISTS public.search_knowledge_chunks_fulltext(text, uuid, int);

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
    content_tokens int,
    page_start int,
    page_end int,
    section text,
    score float
)
LANGUAGE plpgsql
SECURITY INVOKER
SET search_path = public
AS $$
DECLARE
    or_query_sv tsquery;
    or_query_simple tsquery;
    and_query_sv tsquery;
    and_query_simple tsquery;
BEGIN
    -- Build OR queries for matching (high recall)
    or_query_sv := build_or_tsquery('swedish', search_query);
    or_query_simple := build_or_tsquery('simple', search_query);
    
    -- Build AND queries for ranking (precision scoring)
    and_query_sv := plainto_tsquery('swedish', search_query);
    and_query_simple := plainto_tsquery('simple', search_query);
    
    RETURN QUERY
    SELECT
        kc.id AS chunk_id,
        kd.id AS document_id,
        kd.title AS document_title,
        kd.version_num::text AS document_version,
        kc.content AS content,
        kc.content_tokens,
        kc.page_start,
        kc.page_end,
        kc.section,
        -- Score: prefer AND matches (full phrase), fall back to OR match score
        greatest(
            ts_rank_cd(kc.tsv, and_query_sv) * 2.0,      -- AND match in Swedish = highest
            ts_rank_cd(kc.tsv, and_query_simple) * 2.0,   -- AND match in simple
            ts_rank_cd(kc.tsv, or_query_sv),               -- OR match in Swedish
            ts_rank_cd(kc.tsv, or_query_simple)            -- OR match in simple
        )::float AS score
    FROM knowledge_chunks kc
    JOIN knowledge_documents kd ON kd.id = kc.document_id
    JOIN knowledge_collection_documents kcd ON kcd.document_id = kd.id
    WHERE kd.status = 'active'
      AND kcd.collection_id = collection_id_filter
      AND (
          kc.tsv @@ or_query_sv
          OR kc.tsv @@ or_query_simple
      )
    ORDER BY greatest(
        ts_rank_cd(kc.tsv, and_query_sv) * 2.0,
        ts_rank_cd(kc.tsv, and_query_simple) * 2.0,
        ts_rank_cd(kc.tsv, or_query_sv),
        ts_rank_cd(kc.tsv, or_query_simple)
    ) DESC
    LIMIT match_count;
END;
$$;
