-- Migration 001 (Revised v5): Initial Schema
-- Final version adding pgcrypto and feedback rating constraint.

-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- Table for storing uploaded documents with versioning
CREATE TABLE knowledge_documents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    canonical_id UUID NOT NULL DEFAULT gen_random_uuid(),
    version_num INT NOT NULL DEFAULT 1,
    is_latest BOOLEAN NOT NULL DEFAULT TRUE,
    supersedes_document_id UUID,
    title TEXT NOT NULL,
    source TEXT,
    category TEXT,
    product_family TEXT,
    version TEXT,
    language CHAR(2) DEFAULT 'sv',
    status TEXT NOT NULL DEFAULT 'draft' CHECK (status IN ('draft', 'active', 'archived')),
    storage_path TEXT NOT NULL,
    checksum TEXT NOT NULL,
    created_by UUID,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(canonical_id, version_num)
);

-- Add self-referencing foreign key after table creation for stable migration
ALTER TABLE knowledge_documents
ADD CONSTRAINT fk_supersedes_document
FOREIGN KEY (supersedes_document_id)
REFERENCES knowledge_documents(id) ON DELETE SET NULL;

-- Table for storing text chunks from documents
CREATE TABLE knowledge_chunks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id UUID NOT NULL REFERENCES knowledge_documents(id) ON DELETE CASCADE,
    chunk_index INT NOT NULL,
    content TEXT NOT NULL,
    content_hash VARCHAR(64) NOT NULL,
    content_tokens INT,
    embedding VECTOR(1536),
    page_start INT,
    page_end INT,
    section TEXT,
    tags JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(document_id, chunk_index)
);

CREATE INDEX ON knowledge_chunks USING hnsw (embedding vector_cosine_ops);
CREATE INDEX idx_chunks_document_id ON knowledge_chunks(document_id);
CREATE INDEX ON knowledge_chunks (content_hash);

-- Table for organizing documents into collections
CREATE TABLE knowledge_collections (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL UNIQUE,
    description TEXT,
    is_default BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Junction table to link documents to collections
CREATE TABLE knowledge_collection_documents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    collection_id UUID NOT NULL REFERENCES knowledge_collections(id) ON DELETE CASCADE,
    document_id UUID NOT NULL REFERENCES knowledge_documents(id) ON DELETE CASCADE,
    UNIQUE(collection_id, document_id)
);

-- Table for logging user queries
CREATE TABLE knowledge_queries (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID,
    collection_id UUID REFERENCES knowledge_collections(id),
    mode TEXT NOT NULL CHECK (mode IN ('technical', 'sales', 'investor')),
    question TEXT NOT NULL,
    answer TEXT,
    answer_citations JSONB,
    confidence TEXT CHECK (confidence IN ('high', 'medium', 'low')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    latency_ms INT
);

-- Detailed logging of chunks retrieved for each query
CREATE TABLE knowledge_query_chunks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    query_id UUID NOT NULL REFERENCES knowledge_queries(id) ON DELETE CASCADE,
    chunk_id UUID NOT NULL REFERENCES knowledge_chunks(id) ON DELETE CASCADE,
    rank INT NOT NULL,
    score FLOAT NOT NULL,
    UNIQUE(query_id, chunk_id)
);

-- Table for user feedback on query responses
CREATE TABLE knowledge_feedback (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    query_id UUID NOT NULL REFERENCES knowledge_queries(id) ON DELETE CASCADE,
    user_id UUID,
    rating INT CHECK (rating >= 1 AND rating <= 5),
    issue_type TEXT,
    comment TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Table for caching embeddings
CREATE TABLE embeddings_cache (
    content_hash VARCHAR(64) PRIMARY KEY,
    embedding VECTOR(1536) NOT NULL,
    tokens INT NOT NULL,
    model_version TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
