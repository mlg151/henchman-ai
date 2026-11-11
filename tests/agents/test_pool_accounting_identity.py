"""Model-only specialists retain their backend's exact accounting identity."""

from contextlib import asynccontextmanager

import httpx
import pytest
from openai import AsyncOpenAI
from tests.providers.test_runtime_budget import Transport

from henchman.agents.config import AgentConfig
from henchman.agents.pool import AgentPool
from henchman.config.schema import Settings
from henchman.core.eventbus import EventBus
from henchman.core.run_accounting import new_run_budget
from henchman.core.run_budget import BudgetExceeded
from henchman.providers.base import Message
from henchman.providers.factory import create_configured_provider
from henchman.providers.runtime_budget import use_run_budget
from henchman.tools.registry import ToolRegistry


@asynccontextmanager
async def specialist(alias, switched, cap):
    def price(provider, rate, source):
        return {
            "provider": provider, "model": "specialist", "input_per_1k": rate,
            "output_per_1k": rate, "cache_read_per_1k": rate,
            "cache_write_per_1k": rate, "source": source, "as_of": "2026-11-07",
        }

    settings = Settings.model_validate({
        "providers": {
            "default": alias,
            alias: {"api_key": "test", "base_url": "https://alias.invalid/v1", "model": "primary"},
            "openai_compat": {"base_url": "https://other.invalid/v1", "model": "other"},
        },
        "usage": {
            "limits": {"max_cost": cap},
            "prices": [price(alias, "1", "exact-alias-catalog"),
                       price("openai_compat", "0", "unrelated-free-catalog")],
        },
    })
    providers = []
    target = create_configured_provider(settings.providers)
    providers.append(target)
    initial = target
    if switched:
        initial = create_configured_provider(settings.providers, provider_name="openai_compat")
        providers.append(initial)
    pool = AgentPool(
        {"probe": AgentConfig(name="Probe", role="probe", description="Probe", model="specialist", tools=["read_file"])},
        initial, None, ToolRegistry(), EventBus(), provider_settings=settings.providers,
    )
    agent = pool.get_agent("probe")
    providers.append(agent.provider)
    agent.messages.append(Message("user", "retained history"))
    if switched:
        pool.set_default_provider(target)
        assert pool.get_agent("probe") is agent
        assert agent.messages[-1].content == "retained history"
        providers.append(agent.provider)
    provider = agent.provider
    await provider._client.close()
    transport = Transport(False)
    provider._client = AsyncOpenAI(
        api_key="test", base_url=provider.base_url,
        http_client=httpx.AsyncClient(transport=httpx.MockTransport(transport)),
    )
    scope = new_run_budget(settings, target)
    try:
        yield provider, scope, transport
    finally:
        for provider in providers:
            await provider._client.close()


@pytest.mark.parametrize("alias", ["openai", "groq", "together", "fireworks"])
@pytest.mark.parametrize("switched", [False, True])
async def test_model_only_specialist_cannot_use_another_catalog_to_bypass_zero_cap(alias, switched):
    async with specialist(alias, switched, "0") as (provider, scope, transport):
        with use_run_budget(scope), pytest.raises(BudgetExceeded, match="money_limit"):
            _ = [chunk async for chunk in provider.chat_completion_stream([Message("user", "test")], max_tokens=7)]
        assert not transport.requests
        assert scope.ledger.snapshot().consumed_requests == 0


@pytest.mark.parametrize("alias", ["openai", "groq", "together", "fireworks"])
@pytest.mark.parametrize("switched", [False, True])
async def test_model_only_specialist_records_exact_alias_price_and_source(alias, switched):
    async with specialist(alias, switched, "1") as (provider, scope, transport):
        with use_run_budget(scope):
            _ = [chunk async for chunk in provider.chat_completion_stream([Message("user", "test")], max_tokens=7)]
        assert len(transport.requests) == 1
        assert transport.requests[0]["model"] == "specialist"
        record = scope.ledger.snapshot().records[0]
        assert record.provider == alias
        assert record.model == "specialist"
        assert record.estimate.pricing.source == "exact-alias-catalog"
        assert record.estimate.pricing.as_of == "2026-11-07"
        assert record.accounted_cost > 0
