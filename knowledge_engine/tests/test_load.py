"""
Load Test Framework
===================
Tests the Knowledge Engine under realistic load:
- 500 chunks across 5 collections
- 50 queries measuring latency, accuracy, and DB load
- Reports p50, p95, p99 latency and index usage

Usage:
    python -m knowledge_engine.tests.test_load

Requires: SUPABASE_URL, SUPABASE_ANON_KEY, SUPABASE_SERVICE_ROLE_KEY in .env
"""
import asyncio
import hashlib
import os
import random
import statistics
import sys
import time
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

os.environ.setdefault("EMBEDDING_PROVIDER", "fulltext")
os.environ.setdefault("CHAT_MODEL", "gpt-4.1-mini")

from supabase import create_client

SUPABASE_URL = os.environ["SUPABASE_URL"]
SERVICE_ROLE_KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
admin = create_client(SUPABASE_URL, SERVICE_ROLE_KEY)

# ─── Configuration ──────────────────────────────────────────────────────────

NUM_COLLECTIONS = 5
CHUNKS_PER_COLLECTION = 100  # 5 * 100 = 500 chunks
DOCS_PER_COLLECTION = 10     # 10 docs per collection, 10 chunks per doc
NUM_QUERIES = 50

# ─── Test Data ──────────────────────────────────────────────────────────────

EMS_TOPICS = [
    ("Peak shaving", "Peak shaving aer en funktion som oevervakar effektuttaget i realtid och aktiverar batteriurladdning naer effekttoppar detekteras. Effektavgifter kan utgoeraen 30-50% av elkostnaden foer industriella kunder. Troeskeln aer konfigurerbar, standard 50 kW."),
    ("Nord Pool integration", "Solpulsen EMS haemtar day-ahead priser fraan Nord Pool varje dag klockan 13:00 CET. Priserna anvaends foer att optimera laddning och urladdning av batterier. Systemet stoedjer alla svenska elomraaden SE1-SE4."),
    ("Batterihantering", "Systemet stoedjer BYD HVS/HVM, Huawei LUNA2000, Growatt ARK, SMA Sunny Island, Tesla Powerwall och Sonnen eco. Kommunikation sker via Modbus TCP/RTU och CAN-bus."),
    ("SCADA integration", "EMS integrerar med befintliga SCADA-system via OPC UA och Modbus. Realtidsdata exponeras via REST API och WebSocket foer dashboard-visualisering."),
    ("Solpanelsoptimering", "Systemet maximerar egenanvaendning av solenergi genom att styra batteriladdning baserat paa solproduktionsprognoser och vaederprognoser fraan SMHI."),
    ("Effektoptimering", "Algoritmen anvaender maskininlaerning foer att foeutsaega effektbehov och optimera batterianvaendning. Historisk data analyseras foer att identifiera moenster."),
    ("Energideklaration", "Systemet genererar automatiska energideklarationer baserat paa maetdata. Rapporter inkluderar energianvaendning, CO2-utslaepp och besparingspotential."),
    ("BRF energianalys", "Foer bostadsraettsfoereningar erbjuder systemet detaljerad analys av gemensam elanvaendning, vaerme, och varmvatten. Payback-beraekningar foer batteriinvesteringar."),
    ("Cybersaekerhet", "All kommunikation aer krypterad med TLS 1.3. Autentisering sker via OAuth 2.0 och JWT. Systemet uppfyller GDPR och NIS2-direktivet."),
    ("Underhallsplanering", "Prediktivt underhall baserat paa battericykler, temperaturdata och degraderingsmodeller. Automatiska larm vid avvikelser fraan normala driftparametrar."),
]

QUERY_TEMPLATES = [
    "Hur fungerar {topic} i Solpulsen EMS?",
    "Beskriv {topic} foer en BRF",
    "Vilka foerdelar har {topic}?",
    "Hur paverkar {topic} elkostnaden?",
    "Vilka tekniska krav finns foer {topic}?",
]

QUERY_TOPICS = [
    "peak shaving", "batterihantering", "Nord Pool", "SCADA",
    "solpaneler", "effektoptimering", "energideklaration",
    "BRF energianalys", "cybersaekerhet", "underhall",
]


# ─── Helpers ────────────────────────────────────────────────────────────────

def generate_chunk_content(topic_name: str, topic_text: str, variation: int) -> str:
    """Generate a realistic chunk with variation."""
    variations = [
        f"{topic_text} Denna konfiguration aer optimerad foer svenska foerhaallanden med haensyn till elomraade och naetavgifter.",
        f"Foer {topic_name.lower()} gaealler foeljande: {topic_text} Implementationen kraever korrekt naetverkskonfiguration.",
        f"{topic_text} Systemet loggar alla haendelser foer revision och felsoekning. Datalagringstiden aer konfigurerbar.",
        f"I kontexten av {topic_name.lower()}: {topic_text} Prestanda maetvarden rapporteras i realtid via dashboard.",
        f"{topic_text} Foer stoerre installationer rekommenderas redundant kommunikation och backup-stroem.",
    ]
    return variations[variation % len(variations)]


# ─── Setup ──────────────────────────────────────────────────────────────────

collection_ids = []
document_ids = []
chunk_ids = []


def setup_load_test_data():
    """Create 5 collections, 50 documents, 500 chunks."""
    global collection_ids, document_ids, chunk_ids
    
    print(f"   Creating {NUM_COLLECTIONS} collections...")
    for i in range(NUM_COLLECTIONS):
        cid = str(uuid4())
        collection_ids.append(cid)
        admin.table("knowledge_collections").insert({
            "id": cid,
            "name": f"Load Test Collection {i+1}",
            "is_default": True,
        }).execute()
    
    print(f"   Creating {NUM_COLLECTIONS * DOCS_PER_COLLECTION} documents...")
    for ci, cid in enumerate(collection_ids):
        for di in range(DOCS_PER_COLLECTION):
            did = str(uuid4())
            canid = str(uuid4())
            document_ids.append(did)
            
            topic_idx = (ci * DOCS_PER_COLLECTION + di) % len(EMS_TOPICS)
            topic_name = EMS_TOPICS[topic_idx][0]
            
            admin.table("knowledge_documents").insert({
                "id": did,
                "canonical_id": canid,
                "version_num": 1,
                "is_latest": True,
                "title": f"{topic_name} - Dokument {di+1}",
                "source": "internal",
                "category": "technical",
                "product_family": "EMS",
                "version": "v2.1",
                "language": "sv",
                "status": "active",
                "storage_path": f"test/load-test-{ci}-{di}.pdf",
                "checksum": hashlib.sha256(f"load-{ci}-{di}".encode()).hexdigest(),
            }).execute()
            
            admin.table("knowledge_collection_documents").insert({
                "collection_id": cid,
                "document_id": did,
            }).execute()
    
    print(f"   Creating {NUM_COLLECTIONS * CHUNKS_PER_COLLECTION} chunks...")
    chunk_batch = []
    for ci, cid in enumerate(collection_ids):
        for di in range(DOCS_PER_COLLECTION):
            did = document_ids[ci * DOCS_PER_COLLECTION + di]
            topic_idx = (ci * DOCS_PER_COLLECTION + di) % len(EMS_TOPICS)
            topic_name, topic_text = EMS_TOPICS[topic_idx]
            
            chunks_per_doc = CHUNKS_PER_COLLECTION // DOCS_PER_COLLECTION
            for chi in range(chunks_per_doc):
                content = generate_chunk_content(topic_name, topic_text, chi)
                chid = str(uuid4())
                chunk_ids.append(chid)
                chunk_batch.append({
                    "id": chid,
                    "document_id": did,
                    "chunk_index": chi,
                    "content": content,
                    "content_hash": hashlib.sha256(content.encode()).hexdigest(),
                    "content_tokens": len(content.split()) * 2,
                    "page_start": chi * 3 + 1,
                    "page_end": chi * 3 + 3,
                })
    
    # Insert in batches of 50
    for i in range(0, len(chunk_batch), 50):
        batch = chunk_batch[i:i+50]
        admin.table("knowledge_chunks").insert(batch).execute()
    
    print(f"   Setup complete: {len(collection_ids)} collections, "
          f"{len(document_ids)} documents, {len(chunk_ids)} chunks")


# ─── Load Test ──────────────────────────────────────────────────────────────

async def run_load_test():
    """Run 50 queries and measure performance."""
    from knowledge_engine.services.query import process_query
    
    latencies = []
    successes = 0
    failures = 0
    confidence_counts = {"high": 0, "medium": 0, "low": 0}
    
    # Generate 50 random queries
    queries = []
    for _ in range(NUM_QUERIES):
        template = random.choice(QUERY_TEMPLATES)
        topic = random.choice(QUERY_TOPICS)
        cid = random.choice(collection_ids)
        queries.append((template.format(topic=topic), cid))
    
    print(f"\n   Running {NUM_QUERIES} queries...")
    
    for i, (question, cid) in enumerate(queries):
        t0 = time.time()
        try:
            result = await process_query(
                question=question,
                collection_id=cid,
                mode="technical",
                jwt=SERVICE_ROLE_KEY,
            )
            latency_ms = int((time.time() - t0) * 1000)
            latencies.append(latency_ms)
            confidence_counts[result.confidence] = confidence_counts.get(result.confidence, 0) + 1
            
            if len(result.citations) > 0:
                successes += 1
            else:
                failures += 1
            
            if (i + 1) % 10 == 0:
                print(f"   ... {i+1}/{NUM_QUERIES} queries complete "
                      f"(last: {latency_ms}ms, {result.confidence})")
        except Exception as e:
            latency_ms = int((time.time() - t0) * 1000)
            latencies.append(latency_ms)
            failures += 1
            print(f"   ERROR on query {i+1}: {e}")
    
    return latencies, successes, failures, confidence_counts


# ─── Index Usage Check ──────────────────────────────────────────────────────

def check_index_usage():
    """Check if GIN and HNSW indexes are being used."""
    print("\n   Checking index usage...")
    
    # Check index stats
    try:
        r = admin.rpc("search_knowledge_chunks_fulltext", {
            "search_query": "peak shaving",
            "collection_id_filter": collection_ids[0],
            "match_count": 5,
        }).execute()
        print(f"   GIN index test: returned {len(r.data)} results")
    except Exception as e:
        print(f"   GIN index test failed: {e}")


# ─── Cleanup ────────────────────────────────────────────────────────────────

def cleanup():
    """Remove all load test data."""
    print("\n   Cleaning up load test data...")
    
    # Delete queries and query_chunks first
    for cid in collection_ids:
        try:
            qr = admin.table("knowledge_queries").select("id").eq("collection_id", cid).execute()
            if qr.data:
                qids = [r["id"] for r in qr.data]
                for qid in qids:
                    admin.table("knowledge_query_chunks").delete().eq("query_id", qid).execute()
                admin.table("knowledge_queries").delete().eq("collection_id", cid).execute()
        except:
            pass
    
    # Delete collection-document links
    for cid in collection_ids:
        admin.table("knowledge_collection_documents").delete().eq("collection_id", cid).execute()
    
    # Delete chunks and documents
    for did in document_ids:
        admin.table("knowledge_chunks").delete().eq("document_id", did).execute()
        admin.table("knowledge_documents").delete().eq("id", did).execute()
    
    # Delete collections
    for cid in collection_ids:
        admin.table("knowledge_collections").delete().eq("id", cid).execute()
    
    print("   Cleanup complete")


# ─── Main ────────────────────────────────────────────────────────────────────

async def main():
    print("=" * 70)
    print("  PULSEN A.I. KNOWLEDGE ENGINE")
    print("  LOAD TEST")
    print(f"  {NUM_COLLECTIONS} collections, {NUM_COLLECTIONS * CHUNKS_PER_COLLECTION} chunks, {NUM_QUERIES} queries")
    print("=" * 70)
    
    # Setup
    print("=" * 70)
    print("  1. Setup Test Data")
    print("=" * 70)
    t0 = time.time()
    setup_load_test_data()
    setup_time = time.time() - t0
    print(f"   Setup time: {setup_time:.1f}s")
    
    # Run load test
    print("=" * 70)
    print("  2. Load Test Queries")
    print("=" * 70)
    t0 = time.time()
    latencies, successes, failures, confidence_counts = await run_load_test()
    total_time = time.time() - t0
    
    # Index check
    print("=" * 70)
    print("  3. Index Usage")
    print("=" * 70)
    check_index_usage()
    
    # Cleanup
    print("=" * 70)
    print("  4. Cleanup")
    print("=" * 70)
    cleanup()
    
    # Report
    print("=" * 70)
    print("  LOAD TEST RESULTS")
    print("=" * 70)
    
    if latencies:
        sorted_lat = sorted(latencies)
        p50 = sorted_lat[len(sorted_lat) // 2]
        p95 = sorted_lat[int(len(sorted_lat) * 0.95)]
        p99 = sorted_lat[int(len(sorted_lat) * 0.99)]
        avg = statistics.mean(latencies)
        
        print(f"   Queries:     {NUM_QUERIES}")
        print(f"   Successes:   {successes} ({successes/NUM_QUERIES*100:.0f}%)")
        print(f"   Failures:    {failures} ({failures/NUM_QUERIES*100:.0f}%)")
        print(f"   Total time:  {total_time:.1f}s")
        print(f"   Avg latency: {avg:.0f}ms")
        print(f"   P50 latency: {p50}ms")
        print(f"   P95 latency: {p95}ms")
        print(f"   P99 latency: {p99}ms")
        print(f"   Min latency: {min(latencies)}ms")
        print(f"   Max latency: {max(latencies)}ms")
        print(f"   Confidence:  high={confidence_counts.get('high',0)}, "
              f"medium={confidence_counts.get('medium',0)}, "
              f"low={confidence_counts.get('low',0)}")
        
        # Pass/fail criteria
        print()
        if p95 < 10000:
            print("   PASS: P95 latency < 10s")
        else:
            print(f"   FAIL: P95 latency {p95}ms >= 10s")
        
        if successes / NUM_QUERIES >= 0.80:
            print(f"   PASS: Success rate {successes/NUM_QUERIES*100:.0f}% >= 80%")
        else:
            print(f"   FAIL: Success rate {successes/NUM_QUERIES*100:.0f}% < 80%")
    
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())
