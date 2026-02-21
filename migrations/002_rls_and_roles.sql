-- Migration 002 (Revised v6): RLS Policies and Roles
-- SECURITY FIX: All user_read policies now target 'authenticated' role only.
-- This prevents anon key from reading any data.

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

-- 4. Helper function to get current user's role
CREATE OR REPLACE FUNCTION get_my_role() RETURNS app_role AS $$
DECLARE
  my_role app_role;
BEGIN
  SELECT role INTO my_role FROM public.user_roles WHERE user_id = auth.uid();
  RETURN COALESCE(my_role, 'readonly');
END;
$$ LANGUAGE plpgsql SECURITY DEFINER SET search_path = public;

-- ─── Admin Policies (full access) ──────────────────────────────────────────
-- Admin policies use get_my_role() check, which requires auth.uid() → authenticated only.
CREATE POLICY admin_all_user_roles ON user_roles FOR ALL USING (get_my_role() = 'admin') WITH CHECK (get_my_role() = 'admin');
CREATE POLICY admin_all_user_collections ON user_collections FOR ALL USING (get_my_role() = 'admin') WITH CHECK (get_my_role() = 'admin');
CREATE POLICY admin_all_documents ON knowledge_documents FOR ALL USING (get_my_role() = 'admin') WITH CHECK (get_my_role() = 'admin');
CREATE POLICY admin_all_chunks ON knowledge_chunks FOR ALL USING (get_my_role() = 'admin') WITH CHECK (get_my_role() = 'admin');
CREATE POLICY admin_all_collections ON knowledge_collections FOR ALL USING (get_my_role() = 'admin') WITH CHECK (get_my_role() = 'admin');
CREATE POLICY admin_all_collection_documents ON knowledge_collection_documents FOR ALL USING (get_my_role() = 'admin') WITH CHECK (get_my_role() = 'admin');
CREATE POLICY admin_all_queries ON knowledge_queries FOR ALL USING (get_my_role() = 'admin') WITH CHECK (get_my_role() = 'admin');
CREATE POLICY admin_all_query_chunks ON knowledge_query_chunks FOR ALL USING (get_my_role() = 'admin') WITH CHECK (get_my_role() = 'admin');
CREATE POLICY admin_all_feedback ON knowledge_feedback FOR ALL USING (get_my_role() = 'admin') WITH CHECK (get_my_role() = 'admin');

-- ─── User Policies (authenticated only) ────────────────────────────────────
-- CRITICAL: All user policies use "TO authenticated" to block anon access.

-- User Roles/Collections: Users can only see their own rows.
CREATE POLICY user_read_own_role ON user_roles FOR SELECT TO authenticated USING (user_id = auth.uid());
CREATE POLICY user_read_own_collections ON user_collections FOR SELECT TO authenticated USING (user_id = auth.uid());

-- Collections: Authenticated users can see default + assigned collections.
CREATE POLICY user_read_collections ON knowledge_collections FOR SELECT TO authenticated
USING (
    is_default = TRUE
    OR id IN (SELECT collection_id FROM user_collections WHERE user_id = auth.uid())
);

-- Collection-Document links: Authenticated users can see links in accessible collections.
CREATE POLICY user_read_collection_documents ON knowledge_collection_documents FOR SELECT TO authenticated
USING (
    collection_id IN (SELECT id FROM knowledge_collections WHERE is_default = true)
    OR collection_id IN (SELECT collection_id FROM user_collections WHERE user_id = auth.uid())
);

-- Documents: Authenticated users can read active documents in accessible collections.
CREATE POLICY user_read_documents ON knowledge_documents FOR SELECT TO authenticated
USING (
    status = 'active'
    AND EXISTS (
        SELECT 1 FROM knowledge_collection_documents kcd
        WHERE kcd.document_id = knowledge_documents.id
        AND (
            kcd.collection_id IN (SELECT id FROM knowledge_collections WHERE is_default = true)
            OR kcd.collection_id IN (SELECT collection_id FROM user_collections WHERE user_id = auth.uid())
        )
    )
);

-- Chunks: Authenticated users can read chunks from active documents in accessible collections.
CREATE POLICY user_read_chunks ON knowledge_chunks FOR SELECT TO authenticated
USING (
    EXISTS (
        SELECT 1 FROM knowledge_documents d
        JOIN knowledge_collection_documents kcd ON kcd.document_id = d.id
        WHERE d.id = knowledge_chunks.document_id
        AND d.status = 'active'
        AND (
            kcd.collection_id IN (SELECT id FROM knowledge_collections WHERE is_default = true)
            OR kcd.collection_id IN (SELECT collection_id FROM user_collections WHERE user_id = auth.uid())
        )
    )
);

-- Queries: Authenticated users can view and insert their own queries.
CREATE POLICY user_read_own_queries ON knowledge_queries FOR SELECT TO authenticated USING (user_id = auth.uid());
CREATE POLICY user_insert_own_queries ON knowledge_queries FOR INSERT TO authenticated WITH CHECK (user_id = auth.uid());

-- Query Chunks: Authenticated users can view chunk details for their own queries.
CREATE POLICY user_read_own_query_chunks ON knowledge_query_chunks FOR SELECT TO authenticated
USING (EXISTS (SELECT 1 FROM knowledge_queries WHERE id = query_id AND user_id = auth.uid()));

-- Feedback: Authenticated users can view/insert feedback for their own queries.
CREATE POLICY user_read_own_feedback ON knowledge_feedback FOR SELECT TO authenticated
USING (EXISTS (SELECT 1 FROM knowledge_queries WHERE id = knowledge_feedback.query_id AND user_id = auth.uid()));

CREATE POLICY user_insert_own_feedback ON knowledge_feedback FOR INSERT TO authenticated
WITH CHECK (EXISTS (SELECT 1 FROM knowledge_queries WHERE id = knowledge_feedback.query_id AND user_id = auth.uid()));
