"""Authentication and authorization for Henchman-AI API."""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends
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
