"""
Supabase client factory.

TWO clients are provided:

1. get_admin_supabase()
   - Uses service_role key via lazy singleton.
   - ONLY for admin flows: document upload, ingestion, activate/archive, maintenance.
   - Never used for user-facing endpoints.

2. get_user_supabase(jwt: str)
   - Uses SUPABASE_ANON_KEY + user's JWT in Authorization header.
   - RLS policies are fully enforced as the authenticated user.
   - Used for: /knowledge/query, /knowledge/collections, /knowledge/feedback.
   - service_role is NEVER involved here.
"""
from supabase import create_client, Client, ClientOptions
from knowledge_engine.core.config import (
    SUPABASE_URL,
    SUPABASE_ANON_KEY,
    get_service_role_key,
)

# Lazy singleton — not created on import, only on first call
_admin_client: Client | None = None


def get_admin_supabase() -> Client:
    """
    Returns a lazy singleton Supabase client using the service_role key.
    ONLY use for admin/backend flows. Never for user-facing requests.
    """
    global _admin_client
    if _admin_client is None:
        _admin_client = create_client(SUPABASE_URL, get_service_role_key())
    return _admin_client


def get_user_supabase(jwt: str) -> Client:
    """
    Returns a Supabase client authenticated with the user's Supabase JWT.
    Uses ANON_KEY as the API key and passes the JWT in the Authorization header.
    RLS policies are fully enforced. service_role is never used.
    """
    client = create_client(
        SUPABASE_URL,
        SUPABASE_ANON_KEY,
        options=ClientOptions(
            headers={"Authorization": f"Bearer {jwt}"}
        ),
    )
    return client
