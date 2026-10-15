"""Model switches accept an explicit session context length."""

from io import StringIO
from types import SimpleNamespace
from typing import Any, cast

import pytest
from rich.console import Console

from henchman.cli.commands import CommandContext
from henchman.cli.commands.model import ModelCommand
from henchman.config.schema import Settings
from henchman.core.agent import Agent
from henchman.providers.ollama import OllamaProvider


def make_context(args: list[str]) -> tuple[CommandContext, StringIO]:
    provider = OllamaProvider(model="old")
    agent = Agent(provider, max_tokens=2000)
    runtime = SimpleNamespace(
        agent=agent, provider=provider,
        settings=Settings(providers={"ollama": {"model": "configured"}}),
    )
    output = StringIO()
    return CommandContext(
        console=Console(file=output, width=140), agent=agent, repl=cast(Any, runtime), args=args,
    ), output


@pytest.mark.parametrize("args,model", [
    (["set", "ollama", "small", "--context-length", "4096"], "small"),
    (["set", "ollama", "--context-length=4096"], "configured"),
    (["set", "ollama", "--context-length", "4096", "small"], "small"),
])
async def test_switch_sets_and_reports_context(args: list[str], model: str) -> None:
    ctx, output = make_context(args)
    assert ctx.agent is not None and ctx.repl is not None
    assert ctx.repl.settings is not None
    history = ctx.agent.messages
    await ModelCommand().execute(ctx)
    assert ctx.agent.model == model
    assert ctx.repl.settings.context.max_tokens == 4096
    assert ctx.agent.max_tokens == 3072
    assert ctx.agent.messages is history
    assert "4096" in output.getvalue() and "3072" in output.getvalue()
    ctx.args = []
    output.seek(0)
    output.truncate(0)
    await ModelCommand().execute(ctx)
    assert "4096" in output.getvalue() and "3072" in output.getvalue()


@pytest.mark.parametrize("tail", [
    ["--context-length"], ["--context-length", "0"],
    ["--context-length", "-1"], ["--context-length", "1.5"],
    ["--context-length", "false"], ["--context-length=4096", "--context-length=8192"],
    ["--unknown", "4096"], ["one", "two"],
])
async def test_invalid_switch_arguments_leave_runtime_unchanged(tail: list[str]) -> None:
    ctx, output = make_context(["set", "ollama", *tail])
    assert ctx.agent is not None and ctx.repl is not None
    assert ctx.repl.settings is not None
    original = ctx.agent.provider
    configured = ctx.repl.settings.context.max_tokens
    await ModelCommand().execute(ctx)
    assert ctx.agent.provider is original
    assert ctx.repl.provider is original
    assert ctx.agent.max_tokens == 2000
    assert ctx.repl.settings.context.max_tokens == configured
    assert "Usage:" in output.getvalue()
