"""Health and metrics endpoints for Henchman-AI API."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from henchman.api.auth import verify_api_key
from henchman.api.state import state
from henchman.version import VERSION


class HealthResponse(BaseModel):
    """Health check response model."""

    status: str = Field(default="degraded")
    version: str = Field(default=VERSION)
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


def _build_health_response() -> HealthResponse:
    """Build a health payload from the current runtime state."""
    agent_ready = state.agent is not None
    provider_name = state.settings.providers.default if state.settings else None
    return HealthResponse(
        status="ok" if agent_ready else "degraded",
        version=VERSION,
        provider=provider_name,
        agent_ready=agent_ready,
    )


@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    """Report process liveness and whether the model agent is ready.

    Returns:
        Health status information.
    """
    return _build_health_response()


@router.get(
    "/ready",
    response_model=HealthResponse,
    responses={status.HTTP_503_SERVICE_UNAVAILABLE: {"model": HealthResponse}},
)
async def readiness() -> HealthResponse | JSONResponse:
    """Return deployment readiness, failing when no agent can serve chat."""
    payload = _build_health_response()
    if payload.agent_ready:
        return payload
    return JSONResponse(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        content=payload.model_dump(),
    )


@router.get("/metrics", response_model=MetricsResponse)
async def get_metrics(
    _api_key: Annotated[str | None, Depends(verify_api_key)],
) -> MetricsResponse:
    """Get performance metrics.

    Args:
        _api_key: API key for authentication (provided via dependency injection).

    Returns:
        Performance metrics.
    """
    # Use actual metrics from state if available
    if state.metrics:
        return MetricsResponse(
            requests={
                "total": state.metrics.get("requests_total", 0),
                "successful": state.metrics.get("requests_successful", 0),
                "failed": state.metrics.get("requests_failed", 0),
            },
            tokens={
                "prompt": state.metrics.get("tokens_prompt", 0),
                "completion": state.metrics.get("tokens_completion", 0),
                "total": state.metrics.get("tokens_total", 0),
            },
            tools={
                "total_calls": state.metrics.get("tool_calls_total", 0),
                "successful": state.metrics.get("tool_calls_successful", 0),
                "failed": state.metrics.get("tool_calls_failed", 0),
            },
        )

    # Fallback to placeholder data
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
    _api_key: Annotated[str | None, Depends(verify_api_key)],
) -> UsageResponse:
    """Get token usage and cost information.

    Args:
        _api_key: API key for authentication (provided via dependency injection).

    Returns:
        Usage and cost information.
    """
    # Use actual metrics from state if available
    if state.metrics:
        total_tokens = state.metrics.get("tokens_total", 0)
        # Simple cost estimation: rough average of common model prices
        # This is an approximation - actual cost depends on the model used
        total_cost = total_tokens * 0.001 / 1000  # ~$0.001 per 1K tokens

        # Create a simple daily usage structure
        # Note: This shows cumulative usage, not broken down by actual date
        daily_usage = {
            "current_session": {
                "tokens": total_tokens,
                "cost": total_cost,
            },
        }

        return UsageResponse(
            total_tokens=total_tokens,
            total_cost=total_cost,
            daily_usage=daily_usage,
        )

    # Fallback to placeholder data
    return UsageResponse(
        total_tokens=0,
        total_cost=0.0,
        daily_usage={},
    )
