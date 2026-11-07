"""Explicit process runtimes for older endpoint rendering/authentication tests."""

from typing import Any

from henchman.api.run_accounting import ApiChatRun, ApiChatRuns
from henchman.config.schema import Settings


def install_chat_runtime(state: Any, agent: Any) -> None:
    """Supply the new run boundary while retaining a test's scripted Agent."""
    state.agent = agent
    state.settings = Settings()
    if agent is None:
        state.chat_runs = None
        return
    state.chat_runs = ApiChatRuns(state.settings, lambda _settings: agent)
    history = agent.get_messages_for_api.return_value
    if isinstance(history, list) and history:
        agent.messages = history.copy()
    if isinstance(agent.messages, list) and agent.messages:
        record = ApiChatRun("fixture-run", "unauthenticated-local", agent, None, completed=True)
        state.chat_runs._runs[record.run_id] = record
