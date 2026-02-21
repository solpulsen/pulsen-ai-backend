"""
End-to-end demo script for Pulsen A.I. Knowledge Engine.

Steps:
1. Create a test collection via admin client
2. Create a test document (active, is_latest)
3. Generate embeddings for test chunks using text-embedding-3-small
4. Insert chunks with embeddings
5. Link document to collection
6. Run a query via the RAG pipeline
7. Verify logging in knowledge_queries + knowledge_query_chunks
8. Clean up test data

Usage:
    python -m knowledge_engine.tests.e2e_demo
"""
import asyncio
import json
import os
import sys
from uuid import uuid4

# Ensure project root is on path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from dotenv import load_dotenv
load_dotenv()

from supabase import create_client

# ─── Config ──────────────────────────────────────────────────────────────────

SUPABASE_URL = os.environ["SUPABASE_URL"]
SERVICE_ROLE_KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
ANON_KEY = os.environ["SUPABASE_ANON_KEY"]

admin = create_client(SUPABASE_URL, SERVICE_ROLE_KEY)

# ─── Test Data ───────────────────────────────────────────────────────────────

COLLECTION_ID = str(uuid4())
CANONICAL_ID = str(uuid4())
DOCUMENT_ID = str(uuid4())

TEST_CHUNKS = [
    {
        "content": "Solpulsen EMS (Energy Management System) är ett intelligent energihanteringssystem "
                   "som optimerar solenergi, batterilager och nätanslutning i realtid. Systemet använder "
                   "AI-baserad prediktion för att maximera egenanvändning av solenergi och minimera "
                   "elkostnader. EMS stödjer peak shaving, batterioptimering och dynamisk lastbalansering.",
        "section": "Produktöversikt",
        "chunk_index": 0,
        "page_start": 1,
        "page_end": 1,
    },
    {
        "content": "Solpulsen EMS integrerar med Nord Pool för realtidspriser i zonerna SE1-SE4. "
                   "Systemet hämtar day-ahead priser och intraday-uppdateringar för att optimera "
                   "batteriladdning och -urladdning. Vid låga elpriser laddas batteriet, och vid höga "
                   "priser används batterilagret för att undvika dyra nätköp. Arbitrage-beräkningar "
                   "körs automatiskt varje timme.",
        "section": "Nord Pool Integration",
        "chunk_index": 1,
        "page_start": 2,
        "page_end": 2,
    },
    {
        "content": "Peak shaving-funktionen i Solpulsen EMS övervakar effektuttaget i realtid och "
                   "aktiverar batteriurladdning automatiskt när effekttoppar detekteras. Systemet "
                   "använder en konfigurerbar tröskel (standard 50 kW) och kan reducera effekttoppar "
                   "med upp till 80%. Detta minskar effektavgifter och nätbelastning avsevärt.",
        "section": "Peak Shaving",
        "chunk_index": 2,
        "page_start": 3,
        "page_end": 3,
    },
    {
        "content": "SMHI väderdata används för solproduktionsprediktion. Systemet hämtar GHI "
                   "(Global Horizontal Irradiance), temperatur och molnighet för att förutsäga "
                   "solpanelernas produktion de kommande 48 timmarna. Prediktionen används för "
                   "att optimera batteristrategin och planera energiflöden.",
        "section": "Väderprediktion",
        "chunk_index": 3,
        "page_start": 4,
        "page_end": 4,
    },
]


# ─── Helpers ─────────────────────────────────────────────────────────────────

async def generate_embeddings(texts: list[str]) -> list[list[float]]:
    """Generate embeddings using text-embedding-3-small via OpenAI."""
    from openai import AsyncOpenAI
    client = AsyncOpenAI(api_key=os.environ["OPENAI_API_KEY"])
    response = await client.embeddings.create(
        model="text-embedding-3-small",
        input=texts,
    )
    return [item.embedding for item in response.data]


def print_section(title: str):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")


# ─── Setup ───────────────────────────────────────────────────────────────────

async def setup_test_data():
    """Insert test collection, document, and chunks with embeddings."""
    print_section("1. Creating test collection")
    admin.table("knowledge_collections").insert({
        "id": COLLECTION_ID,
        "name": "EMS Testkollektion",
        "description": "Testdata för end-to-end demo",
        "is_default": True,
    }).execute()
    print(f"   Collection ID: {COLLECTION_ID}")

    print_section("2. Creating test document")
    admin.table("knowledge_documents").insert({
        "id": DOCUMENT_ID,
        "canonical_id": CANONICAL_ID,
        "version_num": 1,
        "is_latest": True,
        "title": "Solpulsen EMS Teknisk Dokumentation",
        "source": "internal",
        "category": "technical",
        "product_family": "EMS",
        "version": "v1.0",
        "language": "sv",
        "status": "active",
        "storage_path": "test/ems-tech-doc.pdf",
        "checksum": "test-checksum-e2e-demo",
        "content_hash": "test-content-hash-e2e-demo",
    }).execute()
    print(f"   Document ID: {DOCUMENT_ID}")

    print_section("3. Generating embeddings for chunks")
    chunk_texts = [c["content"] for c in TEST_CHUNKS]
    embeddings = await generate_embeddings(chunk_texts)
    print(f"   Generated {len(embeddings)} embeddings ({len(embeddings[0])} dimensions each)")

    print_section("4. Inserting chunks with embeddings")
    for i, (chunk, embedding) in enumerate(zip(TEST_CHUNKS, embeddings)):
        chunk_id = str(uuid4())
        admin.table("knowledge_chunks").insert({
            "id": chunk_id,
            "document_id": DOCUMENT_ID,
            "chunk_index": chunk["chunk_index"],
            "content": chunk["content"],
            "section": chunk["section"],
            "page_start": chunk["page_start"],
            "page_end": chunk["page_end"],
            "token_count": len(chunk["content"].split()),
            "embedding": embedding,
        }).execute()
        print(f"   Chunk {i}: {chunk['section']} ({chunk_id[:8]}...)")

    print_section("5. Linking document to collection")
    admin.table("knowledge_collection_documents").insert({
        "collection_id": COLLECTION_ID,
        "document_id": DOCUMENT_ID,
    }).execute()
    print("   Linked!")


# ─── Query Test ──────────────────────────────────────────────────────────────

async def run_query_test():
    """Run a query through the full RAG pipeline."""
    from knowledge_engine.services.query import process_query

    print_section("6. Running RAG query")
    
    # Create a fake JWT for testing (admin anon key works for RPC calls)
    # In production, this would be a real user JWT
    test_jwt = ANON_KEY  # anon key acts as a valid JWT for RPC

    question = "Hur fungerar peak shaving i Solpulsen EMS?"
    print(f"   Question: {question}")
    print(f"   Collection: {COLLECTION_ID}")
    print(f"   Mode: technical")
    print()

    result = await process_query(
        collection_id=COLLECTION_ID,
        mode="technical",
        question=question,
        jwt=test_jwt,
        constraints=None,
    )

    print(f"   Query ID: {result.query_id}")
    print(f"   Confidence: {result.confidence}")
    print(f"   Latency: {result.latency_ms} ms")
    print()
    print(f"   ANSWER:")
    print(f"   {result.answer[:500]}")
    print()
    print(f"   CITATIONS ({len(result.citations)}):")
    for c in result.citations:
        print(f"   - {c.document_title} | {c.section} | p.{c.page_start}")
    print()
    print(f"   RETRIEVED CHUNKS ({len(result.retrieved_chunks)}):")
    for rc in result.retrieved_chunks:
        print(f"   #{rc.rank} (score={rc.score:.3f}): {rc.content[:80]}...")

    return result


# ─── Verify Logging ──────────────────────────────────────────────────────────

def verify_logging(query_id: str):
    """Check that the query was logged in knowledge_queries and knowledge_query_chunks."""
    print_section("7. Verifying logging")

    # Check knowledge_queries
    q_result = admin.table("knowledge_queries").select("*").eq("id", query_id).execute()
    if q_result.data:
        q = q_result.data[0]
        print(f"   knowledge_queries: FOUND")
        print(f"   - question: {q['question'][:60]}...")
        print(f"   - confidence: {q['confidence']}")
        print(f"   - mode: {q['mode']}")
        print(f"   - latency_ms: {q['latency_ms']}")
    else:
        print(f"   knowledge_queries: NOT FOUND (logging may have failed)")

    # Check knowledge_query_chunks
    qc_result = admin.table("knowledge_query_chunks").select("*").eq("query_id", query_id).execute()
    if qc_result.data:
        print(f"   knowledge_query_chunks: {len(qc_result.data)} rows")
        for row in qc_result.data:
            print(f"   - rank={row['rank']}, score={row['score']:.3f}, chunk={row['chunk_id'][:8]}...")
    else:
        print(f"   knowledge_query_chunks: NOT FOUND")


# ─── Cleanup ─────────────────────────────────────────────────────────────────

def cleanup():
    """Remove test data."""
    print_section("8. Cleanup")
    try:
        admin.table("knowledge_query_chunks").delete().neq("query_id", "00000000-0000-0000-0000-000000000000").execute()
        admin.table("knowledge_queries").delete().neq("id", "00000000-0000-0000-0000-000000000000").execute()
        admin.table("knowledge_collection_documents").delete().eq("collection_id", COLLECTION_ID).execute()
        admin.table("knowledge_chunks").delete().eq("document_id", DOCUMENT_ID).execute()
        admin.table("knowledge_documents").delete().eq("id", DOCUMENT_ID).execute()
        admin.table("knowledge_collections").delete().eq("id", COLLECTION_ID).execute()
        print("   Test data cleaned up.")
    except Exception as e:
        print(f"   Cleanup warning: {e}")


# ─── Main ────────────────────────────────────────────────────────────────────

async def main():
    print("\n" + "="*60)
    print("  PULSEN A.I. KNOWLEDGE ENGINE — END-TO-END DEMO")
    print("="*60)

    try:
        await setup_test_data()
        result = await run_query_test()
        verify_logging(str(result.query_id))
    except Exception as e:
        print(f"\n   ERROR: {e}")
        import traceback
        traceback.print_exc()
    finally:
        cleanup()

    print("\n" + "="*60)
    print("  DEMO COMPLETE")
    print("="*60 + "\n")


if __name__ == "__main__":
    asyncio.run(main())
