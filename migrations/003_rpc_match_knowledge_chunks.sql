-- Migration 003: Create RPC function match_knowledge_chunks
--
-- DB is already vector(1536). No dimension changes needed.
-- This migration ONLY creates the RPC function for vector search.
--
-- SECURITY: SECURITY INVOKER — runs as the calling user, RLS is enforced.
-- LANGUAGE: sql (pure SQL, clean and fast)

CREATE OR REPLACE FUNCTION public.match_knowledge_chunks(
    query_embedding vector(1536),
    collection_id_filter uuid,
    match_count int DEFAULT 30,
    score_threshold float DEFAULT 0.30
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
LANGUAGE sql
SECURITY INVOKER
SET search_path = public
AS $$
    SELECT
        kc.id AS chunk_id,
        kd.id AS document_id,
        kd.title AS document_title,
        kd.version_num::text AS document_version,
        kc.content,
        kc.content_tokens,
        kc.page_start,
        kc.page_end,
        kc.section,
        (1 - (kc.embedding <=> query_embedding))::float AS score
    FROM knowledge_chunks kc
    JOIN knowledge_documents kd
        ON kd.id = kc.document_id
        AND kd.status = 'active'
    JOIN knowledge_collection_documents kcd
        ON kcd.document_id = kd.id
        AND kcd.collection_id = collection_id_filter
    WHERE kc.embedding IS NOT NULL
        AND (1 - (kc.embedding <=> query_embedding)) >= score_threshold
    ORDER BY kc.embedding <=> query_embedding ASC
    LIMIT match_count;
$$;
