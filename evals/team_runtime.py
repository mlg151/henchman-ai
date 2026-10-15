"""Production team execution and attributed observations for evaluation rigs."""

from __future__ import annotations

import asyncio
import hashlib
import time
from collections.abc import Callable
from copy import deepcopy
from pathlib import Path
from typing import Any

from evals.models import EvalResult, EventObserver, ToolLog
from henchman.agents.orchestrator import Orchestrator
from henchman.cli.headless import run_orchestrator_json
from henchman.config.environment import format_environment_block, gather_environment
from henchman.config.schema import Settings
from henchman.core.agent import Agent
from henchman.core.events import AgentEvent, EventType
from henchman.providers.base import ModelProvider, ToolCall
from henchman.tools.base import ConfirmationRequest
from henchman.tools.registry import ToolRegistry


def create_eval_registry(workspace: Path) -> ToolRegistry:
    """Reuse production tool assembly, excluding unavailable placeholder exports."""
    from henchman.cli.tool_manager import ToolManager
    from henchman.tools.builtins import iter_available_builtin_tool_classes

    manager = ToolManager()
    manager.bind_runtime(project_root=workspace)
    manager.register_builtin_tools()
    available = iter_available_builtin_tool_classes()
    for name in manager.registry.list_tools():
        if type(manager.registry.get(name)) not in available:
            manager.registry.unregister(name)
    return manager.registry


async def _approve_eval_tool(_request: ConfirmationRequest) -> bool:
    """Evaluation workspaces auto-approve tools; they are not OS sandboxes."""
    return True


class ToolObservations:
    """Correlate nested calls by actor and id, preserving request order."""

    def __init__(self, events: list[AgentEvent], logs: list[ToolLog]) -> None:
        self.events = events
        self.logs = logs
        self.pending: dict[tuple[str | None, str], ToolLog] = {}
        self.ambiguous: set[tuple[str | None, str]] = set()
        self.diagnostics: list[str] = []

    def record(self, event: AgentEvent) -> None:
        self.events.append(event)
        if event.type == EventType.TOOL_CALL_REQUEST and isinstance(event.data, ToolCall):
            call = event.data
            log = ToolLog(
                call.name,
                deepcopy(call.arguments),
                "Tool call did not complete",
                False,
                source_agent=event.source_agent,
                tool_call_id=call.id,
                request_index=len(self.events) - 1,
            )
            self.logs.append(log)
            key = (event.source_agent, call.id)
            if key in self.pending or key in self.ambiguous:
                message = (
                    f"Ambiguous overlapping tool call id {call.id!r} for {event.source_agent!r}"
                )
                previous = self.pending.pop(key, None)
                if previous is not None:
                    previous.result = message
                log.result = message
                if key not in self.ambiguous:
                    self.diagnostics.append(message)
                self.ambiguous.add(key)
            else:
                self.pending[key] = log
        elif event.type == EventType.TOOL_CALL_RESULT and isinstance(event.data, dict):
            completed = self.pending.pop(
                (event.source_agent, event.data.get("tool_call_id", "")), None
            )
            if completed is not None:
                completed.result = str(event.data.get("result", ""))
                completed.success = event.data.get("success") is True
                completed.result_index = len(self.events) - 1


_TeamObservations = ToolObservations  # Compatibility for existing evaluation consumers.


class TeamEvalRuntime:
    """Own a production orchestrator and temporary evaluation observations."""

    def __init__(
        self,
        provider: ModelProvider,
        settings: Settings,
        workspace: Path,
        events: list[AgentEvent],
        logs: list[ToolLog],
    ) -> None:
        registry = create_eval_registry(workspace)
        registry.set_confirmation_handler(_approve_eval_tool)
        self.orchestrator = Orchestrator(
            provider,
            settings=settings,
            tool_registry=registry,
            environment_context=(
                format_environment_block(gather_environment(workspace)) + "\n\n"
                "Work in the current temporary evaluation project using the team. "
                "Tools are automatically approved; this is not an OS sandbox."
            ),
        )
        self.events = events
        self.logs = logs
        self.last_run_limits: dict[str, Any] | None = None
        self._providers: list[ModelProvider] = [provider]

    def initialize_roles(self) -> None:
        """Create enabled roles after the rig owns this runtime for error cleanup."""
        self._enabled_agents()

    def _capture_providers(self) -> None:
        """Retain actual cached providers without creating or closing any client."""
        for agent in self.orchestrator.pool._agents.values():
            if not any(provider is agent.provider for provider in self._providers):
                self._providers.append(agent.provider)

    @property
    def providers(self) -> list[ModelProvider]:
        """Snapshot providers seen during setup and lazy role execution."""
        self._capture_providers()
        return list(self._providers)

    def _enabled_agents(self) -> dict[str, Agent]:
        pool = self.orchestrator.pool
        try:
            return {
                role: pool.get_agent(role)
                for role, config in pool.configs.items()
                if config.enabled or role == "tech_lead"
            }
        finally:
            self._capture_providers()

    @property
    def metadata(self) -> dict[str, Any]:
        roles = {
            role: self._agent_metadata(agent) for role, agent in self._enabled_agents().items()
        }
        return {
            "profile": "team",
            "scope": "team",
            "roles_preinitialized": True,
            "roles": roles,
            "delegation": self._delegation_limits(),
            "last_run_limits": deepcopy(self.last_run_limits),
        }

    def _delegation_limits(self) -> dict[str, int]:
        settings = self.orchestrator.settings.agents
        return {
            "max_depth": settings.max_delegation_depth,
            "max_turns": settings.max_delegation_turns,
            "max_retries": settings.max_delegation_retries,
        }

    @staticmethod
    def _agent_metadata(agent: Agent) -> dict[str, Any]:
        prompt = agent.system_prompt
        model = agent.model or getattr(agent.provider, "model", None)
        output = agent.provider.prepare_output_budget(min(4096, max(1, agent.context_window // 4)))
        return {
            "provider": agent.provider.name,
            "model": model if isinstance(model, str) else "unspecified",
            "tool_names": sorted(agent.tool_registry.list_tools()),
            "prompt_sha256": hashlib.sha256(prompt.encode("utf-8")).hexdigest(),
            "prompt_chars": len(prompt),
            "max_tokens": agent.max_tokens,
            "context_window": agent.context_window,
            "output_tokens": output.output_tokens,
            "base_tool_iterations": agent.base_tool_iterations,
        }

    async def run(
        self,
        prompt: str,
        max_iterations: int,
        timeout: float,
        *,
        observe_event: Callable[[AgentEvent], None] | None = None,
    ) -> EvalResult:
        """Run with bounded role iterations and authoritative root completion."""
        self.events.clear()
        self.logs.clear()
        observations = ToolObservations(self.events, self.logs)
        observer = EventObserver(observe_event)
        previous: dict[int, tuple[Agent, int]] = {}
        applied: dict[str, dict[str, int]] = {}

        def bound_role(role: str) -> None:
            agent = self.orchestrator.pool.get_agent(role)
            self._capture_providers()
            previous.setdefault(id(agent), (agent, agent.base_tool_iterations))
            agent.base_tool_iterations = max_iterations
            applied[role] = {"base_tool_iterations": max_iterations}

        def record(event: AgentEvent) -> None:
            # Also bound any lazily created target before its execution begins.
            if event.type == EventType.AGENT_STARTED and isinstance(event.data, dict):
                role = event.data.get("agent")
                if role in self.orchestrator.pool.configs:
                    bound_role(role)
            observations.record(event)
            observer(event)

        self.last_run_limits = {
            "max_iterations": max_iterations,
            "timeout": timeout,
            "roles": applied,
            "delegation": self._delegation_limits(),
        }
        started = time.perf_counter()
        success = False
        error: str | None = None
        try:
            for role in self._enabled_agents():
                bound_role(role)
            async with asyncio.timeout(timeout):
                success = await run_orchestrator_json(self.orchestrator, prompt, record)
        except TimeoutError:
            if observer.failed:
                raise
            error = f"Evaluation timed out after {timeout:g}s"
            record(AgentEvent(EventType.ERROR, error, source_agent="orchestrator"))
            record(
                AgentEvent(
                    EventType.FINISHED,
                    {"finish_reason": "error", "task_verified": False},
                    source_agent="orchestrator",
                )
            )
        except Exception as exc:
            if observer.failed:
                raise
            error = str(exc)
            record(AgentEvent(EventType.ERROR, error, source_agent="orchestrator"))
        finally:
            for agent, limit in previous.values():
                agent.base_tool_iterations = limit
        diagnostics = [str(event.data) for event in self.events if event.type == EventType.ERROR]
        diagnostics.extend(observations.diagnostics)
        if observations.diagnostics:
            success = False
            error = error or observations.diagnostics[0]
        if not success and error is None:
            error = (
                diagnostics[-1] if diagnostics else "Evaluation ended without successful completion"
            )
        return EvalResult(
            prompt=prompt,
            final_response="".join(
                str(event.data or "")
                for event in self.events
                if event.type == EventType.CONTENT and event.source_agent == "tech_lead"
            ),
            tool_logs=list(self.logs),
            events=list(self.events),
            duration_ms=(time.perf_counter() - started) * 1000,
            tokens_in=None,
            tokens_out=None,
            success=success,
            error=error,
            diagnostics=diagnostics,
        )
