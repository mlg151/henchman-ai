"""FastAPI server for Henchman-AI API."""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import TYPE_CHECKING, Any

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from henchman.api.endpoints import chat, health
from henchman.api.state import state
from henchman.config import load_settings
from henchman.core import Agent
from henchman.providers import get_default_registry

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator


class HealthResponse(BaseModel):
    """Health check response model."""

    status: str = Field(default="ok")
    version: str = Field(default="0.3.11")
    provider: str | None = Field(default=None)


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

    # Initialize state
    state.settings = load_settings()
    state.provider_registry = get_default_registry()

    # Load API keys from settings
    if state.settings.api and hasattr(state.settings.api, "api_keys"):
        state.api_keys = set(state.settings.api.api_keys)

    # Create default agent
    try:
        provider_name = state.settings.providers.default
        # Get provider settings based on provider name
        provider_settings = _get_provider_settings(provider_name, state.settings)

        provider = state.provider_registry.create(
            provider_name,
            **provider_settings,
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

    # Shutdown
    print("Shutting down Henchman-AI API server...")


# Create FastAPI app
app = FastAPI(
    title="Henchman-AI API",
    description="REST API for Henchman-AI - A model-agnostic AI agent CLI",
    version="0.3.11",
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

# Include routers
app.include_router(chat.router)
app.include_router(health.router)


@app.get("/", include_in_schema=False)
async def root() -> dict[str, str]:
    """Root endpoint."""
    return {
        "message": "Henchman-AI API",
        "version": "0.3.11",
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
    reload: bool = False,
    workers: int = 1,
) -> None:
    """Run the FastAPI server.

    Args:
        host: Host to bind to.
        port: Port to bind to.
        reload: Enable auto-reload for development.
        workers: Number of worker processes.
    """
    import uvicorn

    uvicorn.run(
        "henchman.api.server:app",
        host=host,
        port=port,
        reload=reload,
        workers=workers,
    )
