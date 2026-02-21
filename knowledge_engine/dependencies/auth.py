"""
FastAPI auth dependencies.

All user-facing endpoints (collections, query, feedback) MUST use get_bearer_token.
It extracts and validates the Bearer JWT from the Authorization header.

extract_user_id_from_jwt decodes the sub claim for logging purposes only.
RLS handles actual access control — we do NOT verify the JWT signature here.
"""
import base64
import json
from typing import Optional

from fastapi import Header, HTTPException, status


def get_bearer_token(authorization: str = Header(..., alias="Authorization")) -> str:
    """
    Extracts and validates the Bearer JWT from the Authorization header.
    - Requires the header to be present.
    - Requires the format: 'Bearer <token>'
    - Rejects empty tokens.
    Raises HTTP 401 on any violation.
    """
    if not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authorization header must start with 'Bearer '",
            headers={"WWW-Authenticate": "Bearer"},
        )
    token = authorization.removeprefix("Bearer ").strip()
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Bearer token is empty",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return token


def extract_user_id_from_jwt(jwt: str) -> Optional[str]:
    """
    Decode the JWT payload to extract the 'sub' claim (Supabase user ID).
    Used for logging only — NOT for access control (RLS handles that).
    No signature verification — this is intentional.
    Returns None if decoding fails for any reason.
    """
    try:
        # JWT format: header.payload.signature
        payload_b64 = jwt.split(".")[1]
        # Add padding if needed
        padding = 4 - len(payload_b64) % 4
        if padding != 4:
            payload_b64 += "=" * padding
        payload = json.loads(base64.urlsafe_b64decode(payload_b64))
        return payload.get("sub")
    except Exception:
        return None
