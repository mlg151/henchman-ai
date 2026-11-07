"""Authentication and authorization for Henchman-AI API."""

from __future__ import annotations

from hashlib import sha256
from typing import Annotated

from fastapi import Depends, HTTPException
from fastapi.security import APIKeyHeader

from henchman.api.state import state

# API key security
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


async def verify_api_key(
    api_key: Annotated[str | None, Depends(api_key_header)] = None,
) -> bool:
    """Verify API key.

    Works as a FastAPI dependency — extracts the key from the X-API-Key header
    via ``api_key_header`` and validates it against the configured keys.

    Args:
        api_key: API key extracted from the request header.

    Returns:
        True if API key is valid, False otherwise.
    """
    if not state.settings or not hasattr(state.settings, "api"):
        # Authentication not required
        return True

    if not state.settings.api.require_auth:
        # Authentication disabled
        return True

    if not api_key:
        return False

    return api_key in state.api_keys


async def verified_chat_authority(
    api_key: Annotated[str | None, Depends(api_key_header)] = None,
) -> str:
    """Bind process runs to verified keys, or one explicit local authority."""
    if not await verify_api_key(api_key):
        raise HTTPException(401, "Invalid API key")
    if state.settings is not None and state.settings.api.require_auth:
        assert api_key is not None
        return "api-key:" + sha256(api_key.encode()).hexdigest()
    return "unauthenticated-local"
