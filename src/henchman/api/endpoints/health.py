"""Health and metrics endpoints for Henchman-AI API."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from henchman.api.auth import verify_api_key
from henchman.api.state import state


class HealthResponse(BaseModel):
    """Health check response model."""

    status: str = Field(default="ok")
    version: str = Field(default="0.3.11")
    provider: str | None = Field(default=None)
    agent_ready: bool = Field(default=False)


class MetricsResponse(BaseModel):
    """Metrics response model."""

    requests: dict[str, int] = Field(default_factory=dict)
    tokens: dict[str, int] = Field(default_factory=dict)
    tools: dict[str, int] = Field(default_factory=dict)


class UsageResponse(BaseModel):
    """Usage response model."""

    total_tokens: int = Field(default=0)
    total_cost: float = Field(default=0.0)
    daily_usage: dict[str, dict[str, int | float]] = Field(default_factory=dict)


router = APIRouter(prefix="/v1", tags=["health"])


@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    """Health check endpoint.

    Returns:
        Health status information.
    """
    provider_name = state.settings.providers.default if state.settings else None
    agent_ready = state.agent is not None

    return HealthResponse(
        status="ok",
        version="0.3.11",
        provider=provider_name,
        agent_ready=agent_ready,
    )


@router.get("/metrics", response_model=MetricsResponse)
async def get_metrics(
    _api_key: str | None = Depends(verify_api_key),
) -> MetricsResponse:
    """Get performance metrics.

    Args:
        api_key: API key for authentication.

    Returns:
        Performance metrics.
    """
    # TODO: Implement actual metrics collection
    # For now, return placeholder data

    return MetricsResponse(
        requests={
            "total": 0,
            "successful": 0,
            "failed": 0,
        },
        tokens={
            "prompt": 0,
            "completion": 0,
            "total": 0,
        },
        tools={
            "total_calls": 0,
            "successful": 0,
            "failed": 0,
        },
    )


@router.get("/usage", response_model=UsageResponse)
async def get_usage(
    _api_key: str | None = Depends(verify_api_key),
) -> UsageResponse:
    """Get token usage and cost information.

    Args:
        api_key: API key for authentication.

    Returns:
        Usage and cost information.
    """
    # TODO: Implement actual usage tracking
    # For now, return placeholder data

    return UsageResponse(
        total_tokens=0,
        total_cost=0.0,
        daily_usage={},
    )
