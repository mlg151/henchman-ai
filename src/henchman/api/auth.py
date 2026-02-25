"""Authentication and authorization for Henchman-AI API."""

from __future__ import annotations

from fastapi.security import APIKeyHeader

from henchman.api.state import state

# API key security
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


async def verify_api_key(api_key: str | None = None) -> bool:
    """Verify API key.

    Args:
        api_key: API key from request header.

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
