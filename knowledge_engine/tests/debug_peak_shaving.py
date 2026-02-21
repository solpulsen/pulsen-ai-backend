"""Debug script: insert test data, run peak shaving query, check results, then clean up."""
import asyncio
import hashlib
import os
import sys
from uuid import uuid4

from dotenv import load_dotenv
import pathlib
_test_dir = pathlib.Path(__file__).resolve().parent
for _env in [_test_dir / ".env", _test_dir.parent / ".env"]:
    if _env.exists():
        load_dotenv(str(_env), override=True)
        break

from supabase import create_client

SUPABASE_URL = os.environ["SUPABASE_URL"]
SERVICE_ROLE_KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
admin = create_client(SUPABASE_URL, SERVICE_ROLE_KEY)

COLLECTION_ID = str(uuid4())
DOCUMENT_ID = str(uuid4())
CANONICAL_ID = str(uuid4())

# Test content with "peak shaving"
TEST_CONTENT = """Peak shaving aer en av de mest vaerdefulla funktionerna i Solpulsen EMS. 
Funktionen oevervakar det momentana effektuttaget fraan elnaetet i realtid och aktiverar 
batteriurladdning automatiskt naer effekttoppar detekteras. Effektavgifter kan utgoeraen 
30 till 50 procent av den totala elkostnaden foer industriella kunder och 
bostadsraettsfoereningar med hoeg effektanvaendning. Genom att reducera effekttopparna 
kan Solpulsen EMS avsevaert minska dessa kostnader. Algoritmen anvaender en konfigurerbar 
troeskel som standard aer satt till 50 kW."""


async def main():
    print("=== Setting up test data ===")
    
    # Create collection
    admin.table("knowledge_collections").insert({
        "id": COLLECTION_ID,
        "name": f"Debug Test {COLLECTION_ID[:8]}",
        "is_default": True,
    }).execute()
    
    # Create document
    admin.table("knowledge_documents").insert({
        "id": DOCUMENT_ID,
        "canonical_id": CANONICAL_ID,
        "version_num": 1,
        "is_latest": True,
        "title": "EMS Peak Shaving Guide",
        "source": "internal",
        "status": "active",
        "storage_path": "test/peak-shaving.pdf",
        "checksum": hashlib.sha256(b"test").hexdigest(),
    }).execute()
    
    # Link
    admin.table("knowledge_collection_documents").insert({
        "collection_id": COLLECTION_ID,
        "document_id": DOCUMENT_ID,
    }).execute()
    
    # Insert chunk
    chunk_id = str(uuid4())
    admin.table("knowledge_chunks").insert({
        "id": chunk_id,
        "document_id": DOCUMENT_ID,
        "chunk_index": 0,
        "content": TEST_CONTENT,
        "content_hash": hashlib.sha256(TEST_CONTENT.encode()).hexdigest(),
        "content_tokens": 120,
        "page_start": 5,
        "page_end": 6,
    }).execute()
    
    print(f"   Collection: {COLLECTION_ID}")
    print(f"   Document: {DOCUMENT_ID}")
    print(f"   Chunk: {chunk_id}")
    
    # Check tsvector
    r = admin.table("knowledge_chunks").select("id, tsv").eq("id", chunk_id).execute()
    print(f"   tsvector populated: {r.data[0].get('tsv') is not None}")
    
    # Test RPC directly
    print("\n=== Testing RPC directly ===")
    r = admin.rpc("search_knowledge_chunks_fulltext", {
        "search_query": "peak shaving",
        "collection_id_filter": COLLECTION_ID,
        "match_count": 5,
    }).execute()
    print(f"   RPC results for 'peak shaving': {len(r.data)}")
    for row in r.data:
        print(f"     score={row['score']}, title={row['document_title']}, page={row['page_start']}")
    
    r2 = admin.rpc("search_knowledge_chunks_fulltext", {
        "search_query": "effektavgifter batteri",
        "collection_id_filter": COLLECTION_ID,
        "match_count": 5,
    }).execute()
    print(f"   RPC results for 'effektavgifter batteri': {len(r2.data)}")
    for row in r2.data:
        print(f"     score={row['score']}, title={row['document_title']}")
    
    # Test via process_query
    print("\n=== Testing via process_query ===")
    os.environ["EMBEDDING_PROVIDER"] = "fulltext"
    os.environ["CHAT_MODEL"] = "gpt-4.1-mini"
    
    from knowledge_engine.services.query import process_query
    result = await process_query(
        question="Hur fungerar peak shaving?",
        collection_id=COLLECTION_ID,
        mode="technical",
        jwt=SERVICE_ROLE_KEY,
    )
    print(f"   Answer length: {len(result.answer)}")
    print(f"   Citations: {len(result.citations)}")
    print(f"   Confidence: {result.confidence}")
    print(f"   Answer: {result.answer[:200]}")
    
    # Cleanup
    print("\n=== Cleanup ===")
    try:
        admin.table("knowledge_queries").delete().eq("collection_id", COLLECTION_ID).execute()
    except: pass
    admin.table("knowledge_collection_documents").delete().eq("collection_id", COLLECTION_ID).execute()
    admin.table("knowledge_chunks").delete().eq("document_id", DOCUMENT_ID).execute()
    admin.table("knowledge_documents").delete().eq("id", DOCUMENT_ID).execute()
    admin.table("knowledge_collections").delete().eq("id", COLLECTION_ID).execute()
    print("   Done")


if __name__ == "__main__":
    asyncio.run(main())
