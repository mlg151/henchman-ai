"""Health and metrics endpoints for Henchman-AI API."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from henchman.api.auth import verified_chat_authority, verify_api_key
from henchman.api.endpoints.chat import get_chat_runs
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

    total_tokens: int | None = Field(default=0)
    total_cost: str | None = None
    budget: dict[str, Any] | None = None
    accounting_lifetime: str = "process"
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
    authority: Annotated[str, Depends(verified_chat_authority)],
    run_id: str | None = None,
) -> UsageResponse:
    """Report the selected caller-owned run, with explicit unknown costs."""
    run = get_chat_runs().find(authority, run_id)
    budget = run.budget() if run is not None else None
    total_tokens = None if run is not None else 0
    if budget is not None and budget["unknown_dispatched_requests"] == 0:
        total_tokens = budget["settled_tokens"]
    return UsageResponse(total_tokens=total_tokens, budget=budget)
