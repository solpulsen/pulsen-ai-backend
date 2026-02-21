"""
Pulsen A.I. Knowledge Engine — FastAPI Application Entry Point.

Routes:
  Admin (service_role):
    POST   /api/v1/knowledge/documents          — Upload document
    GET    /api/v1/knowledge/documents           — List documents
    GET    /api/v1/knowledge/documents/{id}      — Get document
    POST   /api/v1/knowledge/documents/{id}/activate
    POST   /api/v1/knowledge/documents/{id}/archive

  User (JWT + RLS):
    GET    /api/v1/knowledge/collections         — List accessible collections
    GET    /api/v1/knowledge/collections/{id}    — Get collection
    GET    /api/v1/knowledge/collections/{id}/documents
    POST   /api/v1/knowledge/query               — RAG query
    POST   /api/v1/knowledge/feedback            — Submit feedback
    GET    /api/v1/knowledge/feedback             — List own feedback
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from knowledge_engine.routers import documents, collections, query, feedback

app = FastAPI(
    title="Pulsen A.I. Knowledge Engine",
    description="Internal RAG system for Solpulsen Energy Hub",
    version="1.0.0",
)

# CORS — restrict in production
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # TODO: restrict to portal domain in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount routers under /api/v1/knowledge
PREFIX = "/api/v1/knowledge"
app.include_router(documents.router, prefix=PREFIX)
app.include_router(collections.router, prefix=PREFIX)
app.include_router(query.router, prefix=PREFIX)
app.include_router(feedback.router, prefix=PREFIX)


@app.get("/health")
async def health():
    return {"status": "ok", "service": "knowledge-engine"}
