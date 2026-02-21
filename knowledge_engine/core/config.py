"""
Core configuration module — FROZEN ARCHITECTURE.

Locked decisions (do not change without migration + full reindex):
- Embedding model: text-embedding-3-small
- Embedding dimensions: 1536
- Vector index: HNSW with vector_cosine_ops
- Chunk size: ~1000 tokens with 125-token overlap
- Chat model: gpt-4.1-mini

SECURITY RULES (non-negotiable):
- SUPABASE_SERVICE_ROLE_KEY: backend admin flows ONLY (upload, ingestion, activate/archive).
  Loaded lazily via get_service_role_key(). User endpoints can start without it.
  Never logged. Never in frontend. Never in code.
- SUPABASE_ANON_KEY: used together with user JWT for all user-facing endpoints.
- OPENAI_API_KEY: set in runtime secrets only, never committed.
- All secrets: os.getenv() only. Zero hardcoded values.
"""
import os
from dotenv import load_dotenv

load_dotenv()

# ═══════════════════════════════════════════════════════════════════════════════
# FROZEN ARCHITECTURE CONSTANTS — DO NOT CHANGE
# Changing these requires: new migration, full reindex, and force-push.
# ═══════════════════════════════════════════════════════════════════════════════

EMBEDDING_MODEL: str = "text-embedding-3-small"
EMBEDDING_DIMENSIONS: int = 1536
VECTOR_INDEX_TYPE: str = "hnsw"
VECTOR_DISTANCE_OP: str = "vector_cosine_ops"

# ─── Supabase ─────────────────────────────────────────────────────────────────
SUPABASE_URL: str = os.environ["SUPABASE_URL"]
SUPABASE_ANON_KEY: str = os.environ["SUPABASE_ANON_KEY"]

# service_role is loaded lazily — does NOT crash app if missing at startup.
_SUPABASE_SERVICE_ROLE_KEY: str | None = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

# ─── Embedding Provider ──────────────────────────────────────────────────────
# "openai"   = text-embedding-3-small (1536 dims) — requires OPENAI_API_KEY
# "fulltext" = Postgres fulltext search (BM25) — no embeddings needed
# Default: "openai" in production, "fulltext" for environments without OpenAI key.
EMBEDDING_PROVIDER: str = os.getenv("EMBEDDING_PROVIDER", "openai")

# ─── Chat Model ───────────────────────────────────────────────────────────────
CHAT_MODEL: str = os.getenv("CHAT_MODEL", "gpt-4.1-mini")

# ─── OpenAI ───────────────────────────────────────────────────────────────────
# Required when EMBEDDING_PROVIDER=openai. Not needed for fulltext.
OPENAI_API_KEY: str | None = os.getenv("OPENAI_API_KEY")

# ─── Chunking (locked) ───────────────────────────────────────────────────────
CHUNK_TARGET_TOKENS: int = 1000
CHUNK_OVERLAP_TOKENS: int = 125
CHUNK_MAX_TOKENS: int = 1200

# ─── Retrieval (tuned) ───────────────────────────────────────────────────────
RETRIEVAL_TOP_K: int = 6
RETRIEVAL_SCORE_THRESHOLD: float = 0.30
WEAK_MATCH_SCORE_THRESHOLD: float = 0.50

# ─── App ──────────────────────────────────────────────────────────────────────
APP_ENV: str = os.getenv("APP_ENV", "production")
API_SECRET_KEY: str = os.getenv("API_SECRET_KEY", "change-me-in-production")


def get_service_role_key() -> str:
    """
    Returns the service_role key.
    Raises RuntimeError if not set — admin flows must configure it explicitly.
    Only call this from get_admin_supabase(). Never log the return value.
    """
    if not _SUPABASE_SERVICE_ROLE_KEY:
        raise RuntimeError(
            "SUPABASE_SERVICE_ROLE_KEY is not set. "
            "This key is required for admin flows only. "
            "Set it in your secure runtime environment."
        )
    return _SUPABASE_SERVICE_ROLE_KEY
