"""
RLS Verification Test
=====================
Proves that Row Level Security policies correctly block unauthorized access.

Tests:
1. Anon key (no user JWT) cannot read knowledge_documents
2. Anon key cannot read knowledge_chunks
3. Anon key cannot insert into knowledge_documents
4. Anon key cannot delete from knowledge_documents
5. Service role CAN read (bypasses RLS) — control test
6. Fulltext RPC with anon key returns empty (SECURITY INVOKER)
7. Admin operations work with service_role
"""
import hashlib
import os
import sys
from uuid import uuid4

# ─── Load .env ──────────────────────────────────────────────────────────────
from dotenv import load_dotenv
import pathlib
_test_dir = pathlib.Path(__file__).resolve().parent
for _env in [_test_dir / ".env", _test_dir.parent / ".env"]:
    if _env.exists():
        load_dotenv(str(_env), override=True)
        break

_REQUIRED = ["SUPABASE_URL", "SUPABASE_ANON_KEY", "SUPABASE_SERVICE_ROLE_KEY"]
missing = [v for v in _REQUIRED if not os.environ.get(v)]
if missing:
    print(f"\n  SECURITY ERROR: Missing: {', '.join(missing)}")
    sys.exit(1)

from supabase import create_client, ClientOptions

SUPABASE_URL = os.environ["SUPABASE_URL"]
ANON_KEY = os.environ["SUPABASE_ANON_KEY"]
SERVICE_ROLE_KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]

# ─── Clients ────────────────────────────────────────────────────────────────

# Anon client: no user JWT, just the anon key
anon_client = create_client(SUPABASE_URL, ANON_KEY)

# Admin client: service_role key (bypasses RLS)
admin_client = create_client(SUPABASE_URL, SERVICE_ROLE_KEY)

# Fake user client: anon key + a fake JWT (should be rejected)
fake_jwt = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJmYWtlLXVzZXItaWQiLCJyb2xlIjoiYXV0aGVudGljYXRlZCIsImV4cCI6OTk5OTk5OTk5OX0.invalid"
fake_user_client = create_client(
    SUPABASE_URL,
    ANON_KEY,
    options=ClientOptions(headers={"Authorization": f"Bearer {fake_jwt}"})
)

# ─── Test Helpers ────────────────────────────────────────────────────────────

passed = 0
failed = 0

def print_pass(msg, detail=""):
    global passed
    passed += 1
    print(f"   PASS: {msg} {detail}")

def print_fail(msg, detail=""):
    global failed
    failed += 1
    print(f"   FAIL: {msg} {detail}")

def assert_test(msg, condition, detail=""):
    if condition:
        print_pass(msg, detail)
    else:
        print_fail(msg, detail)


# ─── Test Data Setup ─────────────────────────────────────────────────────────

COLLECTION_ID = str(uuid4())
DOCUMENT_ID = str(uuid4())
CANONICAL_ID = str(uuid4())
CHUNK_ID = str(uuid4())

def setup_test_data():
    """Insert test data using admin (service_role) client."""
    admin_client.table("knowledge_collections").insert({
        "id": COLLECTION_ID,
        "name": f"RLS Test {COLLECTION_ID[:8]}",
        "is_default": True,
    }).execute()
    
    admin_client.table("knowledge_documents").insert({
        "id": DOCUMENT_ID,
        "canonical_id": CANONICAL_ID,
        "version_num": 1,
        "is_latest": True,
        "title": "RLS Test Document",
        "status": "active",
        "storage_path": "test/rls-test.pdf",
        "checksum": hashlib.sha256(b"rls-test").hexdigest(),
    }).execute()
    
    admin_client.table("knowledge_collection_documents").insert({
        "collection_id": COLLECTION_ID,
        "document_id": DOCUMENT_ID,
    }).execute()
    
    content = "Peak shaving aer en viktig funktion foer att minska effekttoppar."
    admin_client.table("knowledge_chunks").insert({
        "id": CHUNK_ID,
        "document_id": DOCUMENT_ID,
        "chunk_index": 0,
        "content": content,
        "content_hash": hashlib.sha256(content.encode()).hexdigest(),
        "content_tokens": 20,
        "page_start": 1,
        "page_end": 1,
    }).execute()


def cleanup_test_data():
    """Remove all test data."""
    try:
        admin_client.table("knowledge_query_chunks").delete().in_(
            "query_id",
            [r["id"] for r in admin_client.table("knowledge_queries").select("id").eq("collection_id", COLLECTION_ID).execute().data]
        ).execute()
    except: pass
    try:
        admin_client.table("knowledge_queries").delete().eq("collection_id", COLLECTION_ID).execute()
    except: pass
    admin_client.table("knowledge_collection_documents").delete().eq("collection_id", COLLECTION_ID).execute()
    admin_client.table("knowledge_chunks").delete().eq("document_id", DOCUMENT_ID).execute()
    admin_client.table("knowledge_documents").delete().eq("id", DOCUMENT_ID).execute()
    admin_client.table("knowledge_collections").delete().eq("id", COLLECTION_ID).execute()


# ─── RLS Tests ───────────────────────────────────────────────────────────────

def test_anon_cannot_read_documents():
    """Anon key (no user JWT) should return empty results for documents."""
    try:
        r = anon_client.table("knowledge_documents").select("id, title").execute()
        assert_test("Anon cannot read documents", len(r.data) == 0,
                    f"(got {len(r.data)} rows)")
    except Exception as e:
        # Permission denied is also acceptable
        assert_test("Anon cannot read documents (permission denied)", True,
                    f"({type(e).__name__})")


def test_anon_cannot_read_chunks():
    """Anon key should return empty results for chunks."""
    try:
        r = anon_client.table("knowledge_chunks").select("id, content").execute()
        assert_test("Anon cannot read chunks", len(r.data) == 0,
                    f"(got {len(r.data)} rows)")
    except Exception as e:
        assert_test("Anon cannot read chunks (permission denied)", True,
                    f"({type(e).__name__})")


def test_anon_cannot_insert_documents():
    """Anon key should not be able to insert documents."""
    try:
        anon_client.table("knowledge_documents").insert({
            "id": str(uuid4()),
            "canonical_id": str(uuid4()),
            "version_num": 1,
            "is_latest": True,
            "title": "Unauthorized Insert",
            "status": "active",
            "storage_path": "test/unauthorized.pdf",
            "checksum": hashlib.sha256(b"unauthorized").hexdigest(),
        }).execute()
        # If we get here, RLS failed to block
        print_fail("Anon cannot insert documents (insert succeeded!)")
    except Exception as e:
        assert_test("Anon cannot insert documents", True,
                    f"(blocked: {type(e).__name__})")


def test_anon_cannot_delete_documents():
    """Anon key should not be able to delete documents."""
    try:
        r = anon_client.table("knowledge_documents").delete().eq("id", DOCUMENT_ID).execute()
        # Check if the document still exists
        check = admin_client.table("knowledge_documents").select("id").eq("id", DOCUMENT_ID).execute()
        assert_test("Anon cannot delete documents", len(check.data) == 1,
                    "(document still exists)")
    except Exception as e:
        assert_test("Anon cannot delete documents", True,
                    f"(blocked: {type(e).__name__})")


def test_service_role_can_read():
    """Service role should be able to read everything (control test)."""
    r = admin_client.table("knowledge_documents").select("id, title").eq("id", DOCUMENT_ID).execute()
    assert_test("Service role CAN read documents", len(r.data) == 1,
                f"(got {len(r.data)} rows)")
    
    r2 = admin_client.table("knowledge_chunks").select("id").eq("document_id", DOCUMENT_ID).execute()
    assert_test("Service role CAN read chunks", len(r2.data) == 1,
                f"(got {len(r2.data)} rows)")


def test_anon_rpc_returns_empty():
    """Fulltext RPC with anon key (SECURITY INVOKER) should return empty."""
    try:
        r = anon_client.rpc("search_knowledge_chunks_fulltext", {
            "search_query": "peak shaving",
            "collection_id_filter": COLLECTION_ID,
            "match_count": 5,
        }).execute()
        assert_test("Anon RPC returns empty (RLS enforced)", len(r.data) == 0,
                    f"(got {len(r.data)} rows)")
    except Exception as e:
        assert_test("Anon RPC blocked (permission denied)", True,
                    f"({type(e).__name__})")


def test_service_role_rpc_returns_data():
    """Service role RPC should return data (control test)."""
    r = admin_client.rpc("search_knowledge_chunks_fulltext", {
        "search_query": "peak shaving",
        "collection_id_filter": COLLECTION_ID,
        "match_count": 5,
    }).execute()
    assert_test("Service role RPC returns data", len(r.data) > 0,
                f"(got {len(r.data)} rows)")


def test_fake_jwt_cannot_read():
    """A fake/invalid JWT should not grant access."""
    try:
        r = fake_user_client.table("knowledge_documents").select("id, title").execute()
        assert_test("Fake JWT cannot read documents", len(r.data) == 0,
                    f"(got {len(r.data)} rows)")
    except Exception as e:
        assert_test("Fake JWT blocked", True,
                    f"({type(e).__name__})")


def test_anon_cannot_read_queries():
    """Anon should not be able to read query logs."""
    try:
        r = anon_client.table("knowledge_queries").select("id").execute()
        assert_test("Anon cannot read query logs", len(r.data) == 0,
                    f"(got {len(r.data)} rows)")
    except Exception as e:
        assert_test("Anon cannot read query logs (permission denied)", True,
                    f"({type(e).__name__})")


# ─── Main ────────────────────────────────────────────────────────────────────

def main():
    print("=" * 70)
    print("  PULSEN A.I. KNOWLEDGE ENGINE")
    print("  ROW LEVEL SECURITY (RLS) VERIFICATION")
    print("=" * 70)
    
    print("=" * 70)
    print("  Setup: Creating test data with admin client")
    print("=" * 70)
    setup_test_data()
    print_pass("Test data created")
    
    print("=" * 70)
    print("  1. Anon Access Tests (should all be blocked)")
    print("=" * 70)
    test_anon_cannot_read_documents()
    test_anon_cannot_read_chunks()
    test_anon_cannot_insert_documents()
    test_anon_cannot_delete_documents()
    test_anon_cannot_read_queries()
    
    print("=" * 70)
    print("  2. Fake JWT Tests (should be blocked)")
    print("=" * 70)
    test_fake_jwt_cannot_read()
    
    print("=" * 70)
    print("  3. Service Role Tests (should succeed — control)")
    print("=" * 70)
    test_service_role_can_read()
    test_service_role_rpc_returns_data()
    
    print("=" * 70)
    print("  4. RPC with Anon Key (SECURITY INVOKER)")
    print("=" * 70)
    test_anon_rpc_returns_empty()
    
    print("=" * 70)
    print("  Cleanup")
    print("=" * 70)
    cleanup_test_data()
    print_pass("Test data cleaned up")
    
    print("=" * 70)
    print("  RLS TEST SUMMARY")
    print("=" * 70)
    print(f"   PASSED: {passed}")
    print(f"   FAILED: {failed}")
    print(f"   TOTAL:  {passed + failed}")
    if failed == 0:
        print("   STATUS: ALL RLS TESTS PASSED")
    else:
        print(f"   STATUS: {failed} TESTS FAILED")
    print("=" * 70)


if __name__ == "__main__":
    main()
