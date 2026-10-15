"""The reported large-context slash command updates actual runtime agents."""

from io import StringIO
from types import SimpleNamespace
from typing import Any, cast

import pytest
from rich.console import Console

from henchman.agents.orchestrator import Orchestrator
from henchman.cli.commands import CommandContext, parse_command
from henchman.cli.commands.model import ModelCommand, ProviderConfig
from henchman.config.schema import ProviderSettings, Settings
from henchman.providers import OllamaProvider, OpenRouterProvider


async def test_exact_openrouter_command_sets_large_context_across_real_team(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = Settings()
    original = OllamaProvider(model="initial")
    orchestrator = Orchestrator(default_provider=original, settings=settings)
    lead = orchestrator.tech_lead
    cached = orchestrator.pool.get_agent("explorer")
    lead_history, child_history = lead.messages, cached.messages
    replacement = OpenRouterProvider(api_key="offline-test-key", model="xiaomi/mimo-v2.6-pro")

    def construct(
        config: ProviderConfig, providers: ProviderSettings | None = None
    ) -> OpenRouterProvider:
        assert config.name == "openrouter"
        assert config.model == "xiaomi/mimo-v2.6-pro"
        assert providers is settings.providers
        return replacement

    monkeypatch.setattr("henchman.cli.commands.model._create_provider_instance", construct)
    runtime = SimpleNamespace(
        provider=original,
        agent=lead,
        orchestrator=orchestrator,
        settings=settings,
    )
    parsed = parse_command("/model set openrouter xiaomi/mimo-v2.6-pro --context-length 700000")
    assert parsed is not None and parsed[0] == "model"
    output = StringIO()
    ctx = CommandContext(
        console=Console(file=output, width=140),
        args=parsed[1],
        agent=lead,
        repl=cast(Any, runtime),
        settings=settings,
    )

    await ModelCommand().execute(ctx)

    rendered = output.getvalue()
    assert "Switched from ollama to openrouter" in rendered
    assert "Failed to switch" not in rendered
    assert "700000" in rendered and "525000" in rendered
    assert runtime.provider is replacement
    assert settings.context.max_tokens == 700000
    assert orchestrator.pool.context_config.context_window == 700000
    assert orchestrator.pool.context_config.max_tokens == 525000
    for agent in (lead, cached, orchestrator.pool.get_agent("engineer")):
        assert agent.provider is replacement
        assert agent.model == "xiaomi/mimo-v2.6-pro"
        assert agent._config.context_window == 700000
        assert agent.max_tokens == 525000
    assert lead.messages is lead_history
    assert cached.messages is child_history
