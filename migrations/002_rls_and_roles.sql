-- Migration 002 (Revised v5): RLS Policies and Roles
-- Final version adding explicit document SELECT policy and feedback constraints.

-- 1. Create user roles
CREATE TYPE app_role AS ENUM (
    'admin',
    'intern',
    'installer',
    'sales',
    'partner',
    'readonly'
);

-- 2. Create tables for user-role and user-collection mapping
CREATE TABLE user_roles (
    user_id UUID PRIMARY KEY,
    role app_role NOT NULL DEFAULT 'readonly'
);

CREATE TABLE user_collections (
    user_id UUID NOT NULL REFERENCES user_roles(user_id) ON DELETE CASCADE,
    collection_id UUID NOT NULL REFERENCES knowledge_collections(id) ON DELETE CASCADE,
    PRIMARY KEY (user_id, collection_id)
);

-- 3. Enable RLS on ALL data tables
ALTER TABLE user_roles ENABLE ROW LEVEL SECURITY;
ALTER TABLE user_collections ENABLE ROW LEVEL SECURITY;
ALTER TABLE knowledge_documents ENABLE ROW LEVEL SECURITY;
ALTER TABLE knowledge_chunks ENABLE ROW LEVEL SECURITY;
ALTER TABLE knowledge_collections ENABLE ROW LEVEL SECURITY;
ALTER TABLE knowledge_collection_documents ENABLE ROW LEVEL SECURITY;
ALTER TABLE knowledge_queries ENABLE ROW LEVEL SECURITY;
ALTER TABLE knowledge_query_chunks ENABLE ROW LEVEL SECURITY;
ALTER TABLE knowledge_feedback ENABLE ROW LEVEL SECURITY;

-- 4. Define RLS Policies

-- Helper function to get current user's role, secured with a fixed search_path
CREATE OR REPLACE FUNCTION get_my_role() RETURNS app_role AS $$
DECLARE
  my_role app_role;
BEGIN
  SELECT role INTO my_role FROM public.user_roles WHERE user_id = auth.uid();
  RETURN COALESCE(my_role, 'readonly');
END;
$$ LANGUAGE plpgsql SECURITY DEFINER SET search_path = public;

-- Policies for Admins (full access with checks on writes)
CREATE POLICY "Admin full access" ON user_roles FOR ALL USING (get_my_role() = 'admin') WITH CHECK (get_my_role() = 'admin');
CREATE POLICY "Admin full access" ON user_collections FOR ALL USING (get_my_role() = 'admin') WITH CHECK (get_my_role() = 'admin');
CREATE POLICY "Admin full access" ON knowledge_documents FOR ALL USING (get_my_role() = 'admin') WITH CHECK (get_my_role() = 'admin');
CREATE POLICY "Admin full access" ON knowledge_chunks FOR ALL USING (get_my_role() = 'admin') WITH CHECK (get_my_role() = 'admin');
CREATE POLICY "Admin full access" ON knowledge_collections FOR ALL USING (get_my_role() = 'admin') WITH CHECK (get_my_role() = 'admin');
CREATE POLICY "Admin full access" ON knowledge_collection_documents FOR ALL USING (get_my_role() = 'admin') WITH CHECK (get_my_role() = 'admin');
CREATE POLICY "Admin full access" ON knowledge_queries FOR ALL USING (get_my_role() = 'admin') WITH CHECK (get_my_role() = 'admin');
CREATE POLICY "Admin full access" ON knowledge_query_chunks FOR ALL USING (get_my_role() = 'admin') WITH CHECK (get_my_role() = 'admin');
CREATE POLICY "Admin full access" ON knowledge_feedback FOR ALL USING (get_my_role() = 'admin') WITH CHECK (get_my_role() = 'admin');

-- Policies for Non-Admin Users

-- User Roles/Collections: Users can only see their own rows, no client writes.
CREATE POLICY "User can view their own role" ON user_roles FOR SELECT USING (user_id = auth.uid());
CREATE POLICY "User can view their own collection grants" ON user_collections FOR SELECT USING (user_id = auth.uid());

-- Collections: Users can see collections they are assigned to or that are public.
CREATE POLICY "User read access to assigned/public collections" ON knowledge_collections FOR SELECT
USING (
    is_default = TRUE OR
    id IN (SELECT collection_id FROM user_collections WHERE user_id = auth.uid())
);

-- Collection Documents Junction: Explicitly check collection access.
CREATE POLICY "User read access to document links in accessible collections" ON knowledge_collection_documents FOR SELECT
USING (
    EXISTS (
        SELECT 1 FROM knowledge_collections kc
        WHERE kc.id = knowledge_collection_documents.collection_id
          AND (kc.is_default = TRUE OR kc.id IN (SELECT collection_id FROM user_collections WHERE user_id = auth.uid()))
    )
);

-- Documents: (NEW) Explicit SELECT policy for non-admins.
CREATE POLICY "User read access to active documents in accessible collections" ON knowledge_documents FOR SELECT
USING (
    get_my_role() <> 'admin' AND
    status = 'active' AND (
        EXISTS (
            SELECT 1 FROM knowledge_collection_documents kcd
            JOIN knowledge_collections kc ON kcd.collection_id = kc.id
            WHERE kcd.document_id = knowledge_documents.id AND kc.is_default = TRUE
        )
        OR
        EXISTS (
            SELECT 1 FROM knowledge_collection_documents kcd
            JOIN user_collections uc ON kcd.collection_id = uc.collection_id
            WHERE kcd.document_id = knowledge_documents.id AND uc.user_id = auth.uid()
        )
    )
);

-- Chunks: Explicitly check document status and collection access.
CREATE POLICY "User read access to chunks in accessible documents" ON knowledge_chunks FOR SELECT
USING (
    EXISTS (
        SELECT 1 FROM knowledge_documents kd
        WHERE kd.id = knowledge_chunks.document_id
        -- RLS on knowledge_documents is implicitly applied here, checking status and collection access
    )
);

-- Queries: Users can view and insert their own queries.
CREATE POLICY "User can view their own queries" ON knowledge_queries FOR SELECT USING (user_id = auth.uid());
CREATE POLICY "User can insert their own queries" ON knowledge_queries FOR INSERT WITH CHECK (user_id = auth.uid());

-- Query Chunks: Users can view chunk details for their own queries.
CREATE POLICY "User can view chunks for their own queries" ON knowledge_query_chunks FOR SELECT
USING (EXISTS (SELECT 1 FROM knowledge_queries WHERE id = query_id AND user_id = auth.uid()));

-- Feedback: (Revised) Users can SELECT/INSERT feedback tied to their own queries.
CREATE POLICY "User can view feedback for their own queries" ON knowledge_feedback FOR SELECT
USING (EXISTS (SELECT 1 FROM knowledge_queries WHERE id = knowledge_feedback.query_id AND user_id = auth.uid()));

CREATE POLICY "User can insert feedback for their own queries" ON knowledge_feedback FOR INSERT
WITH CHECK (EXISTS (SELECT 1 FROM knowledge_queries WHERE id = knowledge_feedback.query_id AND user_id = auth.uid()));
