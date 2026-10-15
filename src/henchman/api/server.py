"""FastAPI server for Henchman-AI API."""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import TYPE_CHECKING, Any

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel, Field

from henchman.api.endpoints import chat, health, remote
from henchman.api.state import state
from henchman.config import load_settings
from henchman.core import Agent
from henchman.ops.rate_limits import RateLimiter
from henchman.providers import get_default_registry
from henchman.providers.factory import create_configured_provider
from henchman.version import VERSION

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator, Awaitable, Callable

_OPERATIONAL_PROBE_PATHS = frozenset({"/v1/health", "/v1/ready"})


class ErrorResponse(BaseModel):
    """Error response model."""

    error: str = Field(description="Error message")
    code: str = Field(description="Error code")
    details: dict[str, Any] | None = Field(default=None, description="Additional error details")


# State will be initialized in lifespan function


def _get_provider_settings(provider_name: str, settings: Any) -> dict[str, Any]:
    """Get provider settings for the given provider name.

    Args:
        provider_name: Name of the provider (e.g., "deepseek", "openai")
        settings: The loaded settings object

    Returns:
        Dictionary of provider settings, or empty dict if not found
    """
    # Map provider names to their settings attribute names
    provider_settings_map = {
        "deepseek": "deepseek",
        "openai": "openai",
        "anthropic": "anthropic",
        "ollama": "ollama",
        "openrouter": "openrouter",
        "openai_compat": "openai_compat",
        "together": "together",
        "groq": "groq",
        "fireworks": "fireworks",
    }

    if provider_name not in provider_settings_map:
        return {}

    settings_attr = provider_settings_map[provider_name]
    provider_settings = getattr(settings.providers, settings_attr, None)

    if provider_settings:
        return provider_settings  # type: ignore[no-any-return]
    return {}


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncGenerator[None, None]:
    """Lifespan context manager for FastAPI app.

    Args:
        _app: The FastAPI application instance.

    Yields:
        None: This is a context manager that yields control during the app's lifetime.
    """
    # Startup
    print("Starting Henchman-AI API server...")

    state.api_keys = set()
    state.rate_limiter = None  # type: ignore[attr-defined]
    state._rate_limits = {}  # type: ignore[attr-defined]
    try:
        # Initialize state
        state.settings = load_settings()
        state.provider_registry = get_default_registry()

        api_settings = state.settings.api
        state.api_keys = set(api_settings.api_keys)
        state.rate_limiter = RateLimiter()  # type: ignore[attr-defined]
        state._rate_limits = dict(api_settings.rate_limits)  # type: ignore[attr-defined]

        # Create default agent
        try:
            provider_name = state.settings.providers.default
            provider = create_configured_provider(
                state.settings.providers,
                registry=state.provider_registry,
            )
            state.agent = Agent(
                provider=provider,
                system_prompt="",  # Empty system prompt for API server
            )
            print(f"Created agent with provider: {provider_name}")
        except Exception as e:
            print(f"Warning: Failed to create agent: {e}")
            state.agent = None

        yield
    finally:
        state.rate_limiter = None  # type: ignore[attr-defined]
        state._rate_limits = {}  # type: ignore[attr-defined]
        print("Shutting down Henchman-AI API server...")


# Create FastAPI app
app = FastAPI(
    title="Henchman-AI API",
    description="REST API for Henchman-AI - A model-agnostic AI agent CLI",
    version=VERSION,
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure via settings in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def rate_limit_middleware(
    request: Request,
    call_next: Callable[[Request], Awaitable[Response]],
) -> Response:
    """Rate-limit incoming requests based on client IP.

    Operational liveness and readiness probes bypass rate limiting. Other
    requests check ``X-Forwarded-For`` (first address in chain), then
    ``X-Real-IP``, then ``request.client.host``.  Uses the
    configured ``state.rate_limiter`` if one exists and rate limits are
    stored on ``state._rate_limits`` (populated by the lifespan handler).
    """
    if request.url.path in _OPERATIONAL_PROBE_PATHS:
        return await call_next(request)

    rate_limiter = getattr(state, "rate_limiter", None)
    if rate_limiter is None:
        return await call_next(request)

    # Extract client IP from proxy headers or direct connection
    forwarded = request.headers.get("X-Forwarded-For", "")
    if forwarded:
        client_ip = forwarded.split(",")[0].strip()
    else:
        client_ip = request.headers.get("X-Real-IP", "")
    if not client_ip and request.client:
        client_ip = request.client.host

    if not client_ip:
        return await call_next(request)

    # Read rate limits from state._rate_limits (may be pre-set by tests or
    # lazy-initialized from settings on the first request).
    rate_limits = getattr(state, "_rate_limits", None)
    if rate_limits is None:
        # Lazy-init from settings (the lifespan may have set these already,
        # but tests can override by setting state._rate_limits directly).
        rate_limits = {}
        if state.settings and hasattr(state.settings, "api") and state.settings.api:
            rate_limits = getattr(state.settings.api, "rate_limits", {})
        state._rate_limits = rate_limits  # type: ignore[attr-defined]

    if not rate_limits:
        return await call_next(request)

    # Apply the default rate limit
    default_limit = rate_limits.get("default")
    if not default_limit:
        return await call_next(request)

    if not rate_limiter.allow(client_ip, default_limit):
        return JSONResponse(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            content=ErrorResponse(
                error="Rate limit exceeded",
                code="RATE_LIMIT_EXCEEDED",
            ).model_dump(),
        )

    return await call_next(request)


# Include routers
app.include_router(chat.router)
app.include_router(health.router)
app.include_router(remote.router)


@app.get("/", include_in_schema=False)
async def root() -> dict[str, str]:
    """Root endpoint.

    Returns:
        dict[str, str]: A dictionary containing API information with keys:
            - "message": The API name ("Henchman-AI API")
            - "version": The API version string
            - "docs": The URL path to API documentation ("/docs")
    """
    return {
        "message": "Henchman-AI API",
        "version": VERSION,
        "docs": "/docs",
    }


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    """Handle HTTP exceptions.

    Args:
        request: The incoming HTTP request.
        exc: The HTTP exception that was raised.

    Returns:
        JSONResponse: A JSON response with error details.
    """
    return JSONResponse(
        status_code=exc.status_code,
        content=ErrorResponse(
            error=exc.detail,
            code=f"HTTP_{exc.status_code}",
            details={"path": request.url.path},
        ).model_dump(),
    )


@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, _exc: Exception) -> JSONResponse:
    """Handle generic exceptions.

    Args:
        request: The incoming HTTP request.
        _exc: The exception that was raised (unused in this handler).

    Returns:
        JSONResponse: A JSON response with internal server error details.
    """
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=ErrorResponse(
            error="Internal server error",
            code="INTERNAL_ERROR",
            details={"path": request.url.path},
        ).model_dump(),
    )


def run_server(
    host: str = "127.0.0.1",
    port: int = 8000,
    *,
    reload: bool = False,
    workers: int = 1,
) -> None:
    """Run the FastAPI server.

    Args:
        host: Host to bind to.
        port: Port to bind to.
        reload: Enable auto-reload for development.
        workers: Number of worker processes.

    Returns:
        None: This function runs the server indefinitely and does not return
        unless interrupted.
    """
    import uvicorn

    uvicorn.run(
        "henchman.api.server:app",
        host=host,
        port=port,
        reload=reload,
        workers=workers,
    )
