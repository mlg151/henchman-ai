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
    _api_key: str | None = Depends(verify_api_key),
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
            }
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
