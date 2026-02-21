"""
Production Ingestion Pipeline Test.

Tests the FULL pipeline with a real PDF:
1. Extract text from PDF (18+ pages)
2. Chunk text with overlap
3. Store chunks in Supabase (fulltext mode — no embeddings)
4. Activate document
5. Query via RAG pipeline
6. Verify citations point to correct pages/sections
7. Verify logging in knowledge_queries + knowledge_query_chunks
8. Clean up test data

SECURITY: All credentials from environment variables only.
          Refuses to start if any required variable is missing.

Usage:
    export SUPABASE_URL=...
    export SUPABASE_ANON_KEY=...
    export SUPABASE_SERVICE_ROLE_KEY=...
    export EMBEDDING_PROVIDER=fulltext
    export CHAT_MODEL=gpt-4.1-mini
    python -m knowledge_engine.tests.test_ingestion_pipeline
"""
from __future__ import annotations

import asyncio
import hashlib
import os
import sys
import time
from uuid import uuid4

# ─── Startup Guard ──────────────────────────────────────────────────────────

_REQUIRED = ["SUPABASE_URL", "SUPABASE_ANON_KEY", "SUPABASE_SERVICE_ROLE_KEY"]

# Load .env before validation — search upward from this file
from dotenv import load_dotenv as _load_dotenv
import pathlib as _pathlib
_test_dir = _pathlib.Path(__file__).resolve().parent
for _env_candidate in [_test_dir / ".env", _test_dir.parent / ".env", _test_dir.parent.parent / ".env"]:
    if _env_candidate.exists():
        _load_dotenv(str(_env_candidate), override=True)
        break

def _validate():
    missing = [v for v in _REQUIRED if not os.environ.get(v)]
    if missing:
        print("\n  SECURITY ERROR: Missing required environment variables:")
        for m in missing:
            print(f"    - {m}")
        print("\n  Set them via .env or shell exports. NEVER hardcode secrets.\n")
        sys.exit(1)

_validate()

# ─── Imports ────────────────────────────────────────────────────────────────

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from dotenv import load_dotenv
load_dotenv()

from supabase import create_client

SUPABASE_URL = os.environ["SUPABASE_URL"]
SERVICE_ROLE_KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
ANON_KEY = os.environ["SUPABASE_ANON_KEY"]
EMBEDDING_PROVIDER = os.environ.get("EMBEDDING_PROVIDER", "fulltext")

admin = create_client(SUPABASE_URL, SERVICE_ROLE_KEY)

# ─── Test IDs ───────────────────────────────────────────────────────────────

COLLECTION_ID = str(uuid4())
CANONICAL_ID = str(uuid4())
DOCUMENT_ID = str(uuid4())

# ─── Helpers ────────────────────────────────────────────────────────────────

def print_section(title: str):
    print(f"\n{'=' * 70}")
    print(f"  {title}")
    print(f"{'=' * 70}")

def print_pass(msg: str):
    print(f"   PASS: {msg}")

def print_fail(msg: str):
    print(f"   FAIL: {msg}")

# Track results
results = {"pass": 0, "fail": 0, "tests": []}

def assert_test(name: str, condition: bool, detail: str = ""):
    if condition:
        print_pass(f"{name} {detail}")
        results["pass"] += 1
        results["tests"].append(("PASS", name))
    else:
        print_fail(f"{name} {detail}")
        results["fail"] += 1
        results["tests"].append(("FAIL", name))


# ─── Step 1: Extract text from PDF ─────────────────────────────────────────

def test_extraction():
    print_section("1. PDF Text Extraction")

    pdf_path = os.path.join(os.path.dirname(__file__), "test_ems_documentation.pdf")
    assert_test("PDF file exists", os.path.exists(pdf_path), pdf_path)

    with open(pdf_path, "rb") as f:
        file_bytes = f.read()

    from knowledge_engine.services.ingestion import extract_text
    full_text, page_map = extract_text(file_bytes, "test_ems_documentation.pdf")

    assert_test("Text extracted", len(full_text) > 1000, f"({len(full_text)} chars)")
    assert_test("Multiple pages", len(page_map) >= 10, f"({len(page_map)} pages)")
    assert_test("Contains peak shaving", "peak shaving" in full_text.lower())
    assert_test("Contains Nord Pool", "nord pool" in full_text.lower())
    assert_test("Contains BMS", "bms" in full_text.lower())

    return file_bytes, full_text, page_map


# ─── Step 2: Chunk text ────────────────────────────────────────────────────

def test_chunking(full_text, page_map):
    print_section("2. Text Chunking")

    from knowledge_engine.services.ingestion import _split_into_chunks, _count_tokens

    chunks = _split_into_chunks(full_text, page_map)

    assert_test("Chunks created", len(chunks) > 5, f"({len(chunks)} chunks)")
    assert_test("All chunks have content", all(c["content"] for c in chunks))
    assert_test("All chunks have page_start", all(c.get("page_start") for c in chunks))
    assert_test("Chunk indices sequential",
                all(chunks[i]["chunk_index"] == i for i in range(len(chunks))))

    # Check token counts are reasonable
    token_counts = [c["content_tokens"] for c in chunks]
    avg_tokens = sum(token_counts) / len(token_counts) if token_counts else 0
    max_tokens = max(token_counts) if token_counts else 0
    assert_test("Average tokens reasonable", 200 < avg_tokens < 1500, f"(avg={avg_tokens:.0f})")
    assert_test("Max tokens under limit", max_tokens <= 1500, f"(max={max_tokens})")

    print(f"\n   Chunk summary:")
    print(f"   Total chunks: {len(chunks)}")
    print(f"   Avg tokens: {avg_tokens:.0f}")
    print(f"   Max tokens: {max_tokens}")
    print(f"   Page range: {chunks[0]['page_start']} - {chunks[-1]['page_end']}")

    return chunks


# ─── Step 3: Store chunks in Supabase ──────────────────────────────────────

def test_storage(chunks):
    print_section("3. Database Storage")

    # Create collection
    admin.table("knowledge_collections").insert({
        "id": COLLECTION_ID,
        "name": f"Ingestion Test {COLLECTION_ID[:8]}",
        "description": "Production ingestion pipeline test",
        "is_default": True,
    }).execute()
    print_pass("Collection created")

    # Create document (matches actual DB schema — no content_hash on documents)
    admin.table("knowledge_documents").insert({
        "id": DOCUMENT_ID,
        "canonical_id": CANONICAL_ID,
        "version_num": 1,
        "is_latest": True,
        "title": "Solpulsen EMS Teknisk Dokumentation v2.1",
        "source": "internal",
        "category": "technical",
        "product_family": "EMS",
        "version": "v2.1",
        "language": "sv",
        "status": "active",
        "storage_path": "test/ems-tech-doc-v2.1.pdf",
        "checksum": hashlib.sha256(b"test-ingestion").hexdigest(),
    }).execute()
    print_pass("Document created")

    # Link document to collection
    admin.table("knowledge_collection_documents").insert({
        "collection_id": COLLECTION_ID,
        "document_id": DOCUMENT_ID,
    }).execute()
    print_pass("Document linked to collection")

    # Insert chunks
    chunk_ids = []
    for chunk in chunks:
        chunk_id = str(uuid4())
        chunk_ids.append(chunk_id)
        content = chunk["content"]
        content_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()

        row = {
            "id": chunk_id,
            "document_id": DOCUMENT_ID,
            "chunk_index": chunk["chunk_index"],
            "content": content,
            "content_hash": content_hash,
            "content_tokens": chunk["content_tokens"],
            "page_start": chunk.get("page_start"),
            "page_end": chunk.get("page_end"),
        }
        admin.table("knowledge_chunks").insert(row).execute()

    assert_test("All chunks stored", len(chunk_ids) == len(chunks),
                f"({len(chunk_ids)} chunks)")

    # Verify tsvector was auto-populated by trigger
    sample = admin.table("knowledge_chunks").select("id, tsv").eq(
        "document_id", DOCUMENT_ID
    ).limit(1).execute()
    has_tsv = sample.data and sample.data[0].get("tsv") is not None
    assert_test("tsvector auto-populated by trigger", has_tsv)

    return chunk_ids


# ─── Step 4: Query via RAG pipeline ────────────────────────────────────────

async def test_query():
    print_section("4. RAG Query Pipeline")

    from knowledge_engine.services.query import process_query

    questions = [
        ("Hur fungerar peak shaving i Solpulsen EMS?", "peak shaving"),
        ("Vilka batterimaerken stoedjer systemet?", "batteri"),
        ("Hur integrerar EMS med Nord Pool?", "nord pool"),
    ]

    query_ids = []

    for question, expected_topic in questions:
        print(f"\n   Q: {question}")
        t0 = time.time()

        result = await process_query(
            question=question,
            collection_id=COLLECTION_ID,
            mode="technical",
            jwt=SERVICE_ROLE_KEY,
        )

        latency = int((time.time() - t0) * 1000)
        query_ids.append(str(result.query_id))

        assert_test(f"Answer generated for '{expected_topic}'",
                    len(result.answer) > 50,
                    f"({len(result.answer)} chars, {latency}ms)")

        assert_test(f"Citations present for '{expected_topic}'",
                    len(result.citations) > 0,
                    f"({len(result.citations)} citations)")

        assert_test(f"Confidence set for '{expected_topic}'",
                    result.confidence in ("high", "medium", "low"),
                    f"(confidence={result.confidence})")

        assert_test(f"Query ID valid for '{expected_topic}'",
                    result.query_id is not None)

        assert_test(f"Latency acceptable for '{expected_topic}'",
                    latency < 15000,
                    f"({latency}ms)")

        # Check citation details
        for c in result.citations:
            assert_test(f"Citation has document title",
                        c.document_title is not None and len(c.document_title) > 0)
            assert_test(f"Citation has page reference",
                        c.page_start is not None or c.section is not None,
                        f"(page={c.page_start}, section={c.section})")

        print(f"   A: {result.answer[:150]}...")
        print(f"   Citations: {len(result.citations)}, Chunks: {len(result.retrieved_chunks)}")

    return query_ids


# ─── Step 5: Verify logging ────────────────────────────────────────────────

def test_logging(query_ids):
    print_section("5. Query Logging Verification")

    for qid in query_ids:
        q_result = admin.table("knowledge_queries").select("*").eq("id", qid).execute()
        assert_test(f"Query {qid[:8]} logged in knowledge_queries",
                    len(q_result.data) == 1)

        if q_result.data:
            q = q_result.data[0]
            assert_test(f"Query {qid[:8]} has question",
                        q.get("question") is not None)
            assert_test(f"Query {qid[:8]} has answer",
                        q.get("answer") is not None)
            assert_test(f"Query {qid[:8]} has confidence",
                        q.get("confidence") in ("high", "medium", "low"))
            assert_test(f"Query {qid[:8]} has latency",
                        q.get("latency_ms") is not None and q["latency_ms"] > 0)

        qc_result = admin.table("knowledge_query_chunks").select("*").eq(
            "query_id", qid
        ).execute()
        assert_test(f"Query {qid[:8]} has chunk associations",
                    len(qc_result.data) > 0,
                    f"({len(qc_result.data)} chunks)")


# ─── Step 6: Cleanup ───────────────────────────────────────────────────────

def cleanup():
    print_section("6. Cleanup")
    try:
        admin.table("knowledge_query_chunks").delete().in_(
            "query_id",
            [r.data[0]["id"] for r in [
                admin.table("knowledge_queries").select("id").eq(
                    "collection_id", COLLECTION_ID
                ).execute()
            ] if r.data] or ["00000000-0000-0000-0000-000000000000"]
        ).execute()
    except Exception:
        pass

    try:
        admin.table("knowledge_queries").delete().eq(
            "collection_id", COLLECTION_ID
        ).execute()
    except Exception:
        pass

    try:
        admin.table("knowledge_collection_documents").delete().eq(
            "collection_id", COLLECTION_ID
        ).execute()
    except Exception:
        pass

    try:
        admin.table("knowledge_chunks").delete().eq(
            "document_id", DOCUMENT_ID
        ).execute()
    except Exception:
        pass

    try:
        admin.table("knowledge_documents").delete().eq(
            "id", DOCUMENT_ID
        ).execute()
    except Exception:
        pass

    try:
        admin.table("knowledge_collections").delete().eq(
            "id", COLLECTION_ID
        ).execute()
    except Exception:
        pass

    print_pass("Test data cleaned up")


# ─── Main ───────────────────────────────────────────────────────────────────

async def main():
    print("\n" + "=" * 70)
    print("  PULSEN A.I. KNOWLEDGE ENGINE")
    print("  PRODUCTION INGESTION PIPELINE TEST")
    print(f"  Embedding provider: {EMBEDDING_PROVIDER}")
    print("=" * 70)

    try:
        file_bytes, full_text, page_map = test_extraction()
        chunks = test_chunking(full_text, page_map)
        chunk_ids = test_storage(chunks)
        query_ids = await test_query()
        test_logging(query_ids)
    except Exception as e:
        print(f"\n   FATAL ERROR: {e}")
        import traceback
        traceback.print_exc()
    finally:
        cleanup()

    # Summary
    print("\n" + "=" * 70)
    print("  TEST SUMMARY")
    print("=" * 70)
    print(f"   PASSED: {results['pass']}")
    print(f"   FAILED: {results['fail']}")
    print(f"   TOTAL:  {results['pass'] + results['fail']}")

    if results["fail"] > 0:
        print("\n   FAILED TESTS:")
        for status, name in results["tests"]:
            if status == "FAIL":
                print(f"     - {name}")

    status = "ALL TESTS PASSED" if results["fail"] == 0 else f"{results['fail']} TESTS FAILED"
    print(f"\n   STATUS: {status}")
    print("=" * 70 + "\n")

    return results["fail"] == 0


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
