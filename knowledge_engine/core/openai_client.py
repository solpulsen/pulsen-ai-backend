"""
OpenAI client module — chat completions only.
Uses the new openai>=1.0 client pattern (AsyncOpenAI).

Embeddings are handled by the Embedding Provider (core/embeddings.py).
This module is ONLY for LLM chat completions (RAG answer generation).
"""
from openai import AsyncOpenAI
from knowledge_engine.core.config import CHAT_MODEL

# Lazy singleton — uses default env vars (OPENAI_API_KEY, OPENAI_BASE_URL)
_client: AsyncOpenAI | None = None


def get_openai() -> AsyncOpenAI:
    """Returns a lazy singleton async OpenAI client."""
    global _client
    if _client is None:
        # Uses OPENAI_API_KEY and OPENAI_BASE_URL from environment automatically
        _client = AsyncOpenAI()
    return _client


async def chat_completion(system_prompt: str, user_prompt: str) -> str:
    """
    Generate a chat completion using AsyncOpenAI (openai>=1.0 pattern).
    Low temperature for factual, source-based answers.
    Uses the configured CHAT_MODEL (default: gpt-4.1-mini).
    """
    client = get_openai()
    response = await client.chat.completions.create(
        model=CHAT_MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.1,
    )
    return response.choices[0].message.content or ""
