"""Tests covering missing lines in agents modules.

This module targets specific uncovered code paths in:
- delegation.py
- orchestrator_execution.py
- orchestrator_init.py
- orchestrator_anchoring.py
- orchestrator_events.py
- orchestrator.py
- orchestrator_loop.py
- orchestrator_components.py
- presets.py
- prompts.py
- pool.py
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# delegation.py – missing lines
# ---------------------------------------------------------------------------


class TestDelegationMissingLines:
    """Cover missing paths in delegation.py."""

    def _make_runner(self, **kwargs: Any) -> Any:
        """Create a DelegationRunner for tests."""
        from henchman.agents.delegation import DelegationRunner
        from henchman.config.schema import Settings

        pool = MagicMock()
        settings = Settings()
        shared_context: list = []
        metrics = MagicMock()
        run_agent_loop = AsyncMock()
        assess_completion = MagicMock()

        runner = DelegationRunner(
            pool=pool,
            settings=settings,
            shared_context=shared_context,
            metrics=metrics,
            run_agent_loop=run_agent_loop,
            assess_completion=assess_completion,
        )
        for k, v in kwargs.items():
            setattr(runner, k, v)
        return runner

    def test_agent_protocol_has_clear_history(self) -> None:
        """Line 44: AgentProtocol.clear_history body (ellipsis) is covered."""
        from henchman.agents.delegation import AgentProtocol

        # Create a concrete subclass that inherits the Protocol's `...` body
        class ConcreteAgent(AgentProtocol):  # type: ignore[misc]
            messages: object = []  # type: ignore[assignment]

        agent = ConcreteAgent()
        # Calling the inherited clear_history() covers the `...` on line 44
        agent.clear_history()  # Should execute the `...` body without error

    def test_prepare_execution_agent_messages_none(self) -> None:
        """Lines 166-170: _prepare_execution raises TypeError when messages=None."""
        from henchman.agents.delegation import _prepare_execution
        from henchman.agents.orchestrator_types import DelegationParams

        runner = self._make_runner()

        # Create an agent that passes AgentProtocol but has messages=None
        class AgentWithNoneMessages:
            messages = None

            def clear_history(self) -> None:
                pass

        params = DelegationParams(
            target_role="explorer",
            task="test task",
            brief=None,
            depth=0,
        )
        params.target_agent = AgentWithNoneMessages()

        with pytest.raises(TypeError, match="messages=None"):
            _prepare_execution(runner, params)

    def test_prepare_execution_invalid_message_type(self) -> None:
        """Lines 184-188: _prepare_execution raises TypeError for non-Message objects."""
        from henchman.agents.delegation import _prepare_execution
        from henchman.agents.orchestrator_types import DelegationParams

        runner = self._make_runner()

        # Create an agent that passes AgentProtocol but has wrong message objects
        class AgentWithBadMessages:
            messages = ["not a message object"]

            def clear_history(self) -> None:
                pass

        params = DelegationParams(
            target_role="explorer",
            task="test task",
            brief=None,
            depth=0,
        )
        params.target_agent = AgentWithBadMessages()

        with pytest.raises(TypeError):
            _prepare_execution(runner, params)

    def test_prepare_execution_no_clear_history(self) -> None:
        """Line 177: _prepare_execution raises TypeError when clear_history is missing."""
        from henchman.agents.delegation import _prepare_execution
        from henchman.agents.orchestrator_types import DelegationParams

        runner = self._make_runner()

        # Agent has messages (non-None) but NO clear_history method
        class AgentNoClearHistory:
            messages = []  # Not None, so passes earlier check

        params = DelegationParams(
            target_role="explorer",
            task="test task",
            brief=None,
            depth=0,
        )
        params.target_agent = AgentNoClearHistory()

        with pytest.raises(TypeError, match="clear_history"):
            _prepare_execution(runner, params)

    def test_prepare_execution_messages_not_sequence(self) -> None:
        """Lines 173-178: _prepare_execution raises TypeError for non-Sequence messages."""
        from henchman.agents.delegation import _prepare_execution
        from henchman.agents.orchestrator_types import DelegationParams

        runner = self._make_runner()

        # messages is an int (not a Sequence)
        class AgentWithIntMessages:
            messages: object = 42  # type: ignore[assignment]

            def clear_history(self) -> None:
                pass

        params = DelegationParams(
            target_role="explorer",
            task="test task",
            brief=None,
            depth=0,
        )
        params.target_agent = AgentWithIntMessages()

        with pytest.raises(TypeError):
            _prepare_execution(runner, params)

    def test_prepare_execution_clear_history_attribute_error(self) -> None:
        """Lines 195-200: _prepare_execution handles AttributeError from clear_history."""
        from henchman.agents.delegation import _prepare_execution
        from henchman.agents.orchestrator_types import DelegationParams
        from henchman.providers.base import Message

        runner = self._make_runner()
        real_msg = Message(role="user", content="hello")

        class AgentThatRaisesAttrError:
            messages = [real_msg]

            def clear_history(self) -> None:
                raise AttributeError("missing method")

        params = DelegationParams(
            target_role="explorer",
            task="test task",
            brief=None,
            depth=0,
        )
        params.target_agent = AgentThatRaisesAttrError()

        with pytest.raises(AttributeError):
            _prepare_execution(runner, params)

    def test_prepare_execution_clear_history_exception(self) -> None:
        """Lines 201-205: _prepare_execution re-raises exceptions from clear_history."""
        from henchman.agents.delegation import _prepare_execution
        from henchman.agents.orchestrator_types import DelegationParams
        from henchman.providers.base import Message

        runner = self._make_runner()
        real_msg = Message(role="user", content="hello")

        class AgentThatFailsOnClear:
            messages = [real_msg]

            def clear_history(self) -> None:
                raise RuntimeError("clear failed")

        params = DelegationParams(
            target_role="explorer",
            task="test task",
            brief=None,
            depth=0,
        )
        params.target_agent = AgentThatFailsOnClear()

        with pytest.raises(RuntimeError, match="clear failed"):
            _prepare_execution(runner, params)

    def test_prepare_execution_clear_history_not_callable(self) -> None:
        """Line 170: _prepare_execution raises TypeError when clear_history is not callable."""
        from henchman.agents.delegation import _prepare_execution
        from henchman.agents.orchestrator_types import DelegationParams

        runner = self._make_runner()

        # clear_history is an int, not callable
        class AgentWithNonCallableClearHistory:
            messages = []
            clear_history = 42  # Not callable!

        params = DelegationParams(
            target_role="explorer",
            task="test task",
            brief=None,
            depth=0,
        )
        params.target_agent = AgentWithNonCallableClearHistory()

        with pytest.raises(TypeError, match="not callable"):
            _prepare_execution(runner, params)

    def test_prepare_execution_string_messages(self) -> None:
        """Line 188: _prepare_execution raises TypeError for string messages."""
        from henchman.agents.delegation import _prepare_execution
        from henchman.agents.orchestrator_types import DelegationParams

        runner = self._make_runner()

        # messages is a string (strings are sequences but not valid)
        class AgentWithStringMessages:
            messages = "invalid messages"  # str is a Sequence but not valid

            def clear_history(self) -> None:
                pass

        params = DelegationParams(
            target_role="explorer",
            task="test task",
            brief=None,
            depth=0,
        )
        params.target_agent = AgentWithStringMessages()

        with pytest.raises(TypeError):
            _prepare_execution(runner, params)

    def test_prepare_execution_broken_sequence_indexing(self) -> None:
        """Lines 206-208: _prepare_execution handles IndexError when indexing messages."""
        from collections.abc import Sequence

        from henchman.agents.delegation import _prepare_execution
        from henchman.agents.orchestrator_types import DelegationParams

        runner = self._make_runner()

        # Create a sequence-like object that raises on indexing
        class BrokenSeq(Sequence):
            def __len__(self):
                return 1  # Claims to have content

            def __getitem__(self, idx):
                raise IndexError("broken")

        class AgentWithBrokenSeq:
            messages = BrokenSeq()

            def clear_history(self) -> None:
                pass

        params = DelegationParams(
            target_role="explorer",
            task="test task",
            brief=None,
            depth=0,
        )
        params.target_agent = AgentWithBrokenSeq()

        with pytest.raises(TypeError, match="invalid"):
            _prepare_execution(runner, params)

    @pytest.mark.anyio
    async def test_finalize_execution_target_none(self) -> None:
        """Line 264: _finalize_execution raises ValueError when target_agent=None."""
        from henchman.agents.delegation import _finalize_execution
        from henchman.agents.orchestrator_types import DelegationParams

        runner = self._make_runner()
        params = DelegationParams(
            target_role="explorer",
            task="test",
            brief=None,
            depth=0,
        )
        params.target_agent = None

        with pytest.raises(ValueError, match="target_agent is None"):
            async for _ in _finalize_execution(runner, params):
                pass

    @pytest.mark.anyio
    async def test_finalize_execution_status_str_raises(self) -> None:
        """Lines 290-292: _finalize_execution handles status where str() fails."""
        from henchman.agents.delegation import _finalize_execution
        from henchman.agents.orchestrator_types import DelegationParams
        from henchman.providers.base import Message

        runner = self._make_runner()
        mock_agent = MagicMock()
        mock_agent.messages = [Message(role="assistant", content="done")]
        mock_agent.get_delegation_errors = MagicMock(return_value=[])

        # Create a status object that has no .value and str() raises
        class BrokenStatus:
            def __str__(self) -> None:  # type: ignore
                raise RuntimeError("str failed")

        runner._process_delegation_results = MagicMock(
            return_value=("summary", {}, BrokenStatus())
        )

        params = DelegationParams(
            target_role="explorer",
            task="test",
            brief=None,
            depth=0,
        )
        params.target_agent = mock_agent
        params.msg_start = 0

        events = []
        async for event in _finalize_execution(runner, params):
            events.append(event)
        assert len(events) == 1
        assert events[0].data["status"] == "UNKNOWN_STATUS"

    @pytest.mark.anyio
    async def test_run_delegation_non_error_event_from_get_agent(self) -> None:
        """Lines 374: yield ERROR when non-error event returned from get_agent."""
        from henchman.agents.delegation import DelegationRunner
        from henchman.agents.orchestrator_types import DelegationParams
        from henchman.config.schema import Settings
        from henchman.core.events import AgentEvent, EventType

        runner = DelegationRunner(
            pool=MagicMock(),
            settings=Settings(),
            shared_context=[],
            metrics=MagicMock(),
            run_agent_loop=AsyncMock(),
            assess_completion=MagicMock(),
        )

        # Return a non-error event from _get_target_agent_with_error_handling
        unexpected_event = AgentEvent(EventType.CONTENT, "unexpected")
        runner._get_target_agent_with_error_handling = AsyncMock(
            return_value=unexpected_event
        )

        params = DelegationParams(
            target_role="explorer",
            task="test",
            brief=None,
            depth=0,
        )

        events = []
        async for event in runner.run_delegation(params):
            events.append(event)

        assert any(e.type == EventType.ERROR for e in events)

    @pytest.mark.anyio
    async def test_run_delegation_prepare_execution_error(self) -> None:
        """Lines 389-396: run_delegation yields ERROR when _prepare_execution fails."""
        from henchman.agents.delegation import DelegationRunner
        from henchman.agents.orchestrator_types import DelegationParams
        from henchman.config.schema import Settings
        from henchman.core.events import EventType
        from henchman.providers.base import Message

        mock_agent = MagicMock()
        mock_agent.messages = [Message(role="user", content="test")]

        runner = DelegationRunner(
            pool=MagicMock(),
            settings=Settings(),
            shared_context=[],
            metrics=MagicMock(),
            run_agent_loop=AsyncMock(),
            assess_completion=MagicMock(),
        )
        runner._get_target_agent_with_error_handling = AsyncMock(return_value=mock_agent)

        # Make _prepare_execution raise
        with patch("henchman.agents.delegation._prepare_execution",
                   side_effect=ValueError("prep failed")):
            params = DelegationParams(
                target_role="explorer",
                task="test",
                brief=None,
                depth=0,
            )
            events = []
            async for event in runner.run_delegation(params):
                events.append(event)

        assert any(e.type == EventType.ERROR for e in events)

    @pytest.mark.anyio
    async def test_run_delegation_finalize_value_error(self) -> None:
        """Lines 413-420: run_delegation handles ValueError from _finalize_execution."""
        from henchman.agents.delegation import DelegationRunner
        from henchman.agents.orchestrator_types import DelegationParams
        from henchman.config.schema import Settings
        from henchman.core.events import EventType
        from henchman.providers.base import Message

        mock_agent = MagicMock()
        mock_agent.messages = [Message(role="user", content="test")]

        runner = DelegationRunner(
            pool=MagicMock(),
            settings=Settings(),
            shared_context=[],
            metrics=MagicMock(),
            run_agent_loop=AsyncMock(),
            assess_completion=MagicMock(),
        )
        runner._get_target_agent_with_error_handling = AsyncMock(return_value=mock_agent)

        async def empty_loop(*args: Any, **kwargs: Any) -> Any:
            return
            yield  # type: ignore

        with patch("henchman.agents.delegation._prepare_execution"):
            with patch("henchman.agents.delegation._execute_loop",
                       return_value=empty_loop()):
                with patch("henchman.agents.delegation._finalize_execution") as mock_fin:
                    async def raise_value_error(*a: Any) -> Any:
                        raise ValueError("finalize failed")
                        yield  # type: ignore

                    mock_fin.return_value = raise_value_error()
                    params = DelegationParams(
                        target_role="explorer",
                        task="test",
                        brief=None,
                        depth=0,
                    )
                    events = []
                    async for event in runner.run_delegation(params):
                        events.append(event)

        assert any(e.type == EventType.ERROR for e in events)

    @pytest.mark.anyio
    async def test_get_target_agent_not_protocol(self) -> None:
        """Lines 468-474: _get_target_agent_with_error_handling returns ERROR for non-protocol."""
        from henchman.agents.delegation import DelegationRunner
        from henchman.config.schema import Settings
        from henchman.core.events import EventType

        pool = MagicMock()
        # An object without messages or clear_history
        non_protocol_agent = object()
        pool.get_agent.return_value = non_protocol_agent

        runner = DelegationRunner(
            pool=pool,
            settings=Settings(),
            shared_context=[],
            metrics=MagicMock(),
            run_agent_loop=AsyncMock(),
            assess_completion=MagicMock(),
        )

        result = await runner._get_target_agent_with_error_handling("explorer")
        from henchman.core.events import AgentEvent
        assert isinstance(result, AgentEvent)
        assert result.type == EventType.ERROR

    @pytest.mark.anyio
    async def test_get_target_agent_messages_none(self) -> None:
        """Lines 478-482: _get_target_agent returns ERROR when messages=None."""
        from henchman.agents.delegation import DelegationRunner
        from henchman.config.schema import Settings
        from henchman.core.events import EventType

        # Use a real class that passes AgentProtocol check but has messages=None
        class AgentNoneMessages:
            messages: object = None

            def clear_history(self) -> None:
                pass

        pool = MagicMock()
        pool.get_agent.return_value = AgentNoneMessages()

        runner = DelegationRunner(
            pool=pool,
            settings=Settings(),
            shared_context=[],
            metrics=MagicMock(),
            run_agent_loop=AsyncMock(),
            assess_completion=MagicMock(),
        )

        result = await runner._get_target_agent_with_error_handling("explorer")
        from henchman.core.events import AgentEvent
        assert isinstance(result, AgentEvent)
        assert result.type == EventType.ERROR

    @pytest.mark.anyio
    async def test_get_target_agent_messages_not_sequence(self) -> None:
        """Lines 486-491: _get_target_agent returns ERROR for non-sequence messages."""
        from henchman.agents.delegation import DelegationRunner
        from henchman.config.schema import Settings
        from henchman.core.events import EventType

        # Use a real class with messages=42 (int, not a Sequence)
        class AgentBadMessages:
            messages: object = 42  # int is not a Sequence

            def clear_history(self) -> None:
                pass

        pool = MagicMock()
        pool.get_agent.return_value = AgentBadMessages()

        runner = DelegationRunner(
            pool=pool,
            settings=Settings(),
            shared_context=[],
            metrics=MagicMock(),
            run_agent_loop=AsyncMock(),
            assess_completion=MagicMock(),
        )

        result = await runner._get_target_agent_with_error_handling("explorer")
        from henchman.core.events import AgentEvent
        assert isinstance(result, AgentEvent)
        assert result.type == EventType.ERROR

    @pytest.mark.anyio
    async def test_get_target_agent_messages_is_string(self) -> None:
        """Lines 527-532: _get_target_agent returns ERROR when messages is a string."""
        from henchman.agents.delegation import DelegationRunner
        from henchman.config.schema import Settings
        from henchman.core.events import EventType

        class AgentStringMessages:
            messages: object = "not a sequence of messages"

            def clear_history(self) -> None:
                pass

        pool = MagicMock()
        pool.get_agent.return_value = AgentStringMessages()

        runner = DelegationRunner(
            pool=pool,
            settings=Settings(),
            shared_context=[],
            metrics=MagicMock(),
            run_agent_loop=AsyncMock(),
            assess_completion=MagicMock(),
        )

        result = await runner._get_target_agent_with_error_handling("explorer")
        from henchman.core.events import AgentEvent
        assert isinstance(result, AgentEvent)
        assert result.type == EventType.ERROR

    @pytest.mark.anyio
    async def test_get_target_agent_no_clear_history(self) -> None:
        """Lines 544-549: _get_target_agent returns ERROR when clear_history missing."""
        from henchman.agents.delegation import DelegationRunner
        from henchman.config.schema import Settings
        from henchman.core.events import EventType
        from henchman.providers.base import Message

        class AgentNoClearHistory:
            messages = [Message(role="user", content="hi")]
            # No clear_history method

        pool = MagicMock()
        pool.get_agent.return_value = AgentNoClearHistory()

        runner = DelegationRunner(
            pool=pool,
            settings=Settings(),
            shared_context=[],
            metrics=MagicMock(),
            run_agent_loop=AsyncMock(),
            assess_completion=MagicMock(),
        )

        result = await runner._get_target_agent_with_error_handling("explorer")
        from henchman.core.events import AgentEvent
        assert isinstance(result, AgentEvent)
        assert result.type == EventType.ERROR

    @pytest.mark.anyio
    async def test_get_target_agent_clear_history_not_callable(self) -> None:
        """Lines 553-557: _get_target_agent returns ERROR when clear_history not callable."""
        from henchman.agents.delegation import DelegationRunner
        from henchman.config.schema import Settings
        from henchman.core.events import EventType
        from henchman.providers.base import Message

        class AgentNonCallableClearHistory:
            messages = [Message(role="user", content="hi")]
            clear_history = "not a function"  # Attribute exists but not callable

        pool = MagicMock()
        pool.get_agent.return_value = AgentNonCallableClearHistory()

        runner = DelegationRunner(
            pool=pool,
            settings=Settings(),
            shared_context=[],
            metrics=MagicMock(),
            run_agent_loop=AsyncMock(),
            assess_completion=MagicMock(),
        )

        result = await runner._get_target_agent_with_error_handling("explorer")
        from henchman.core.events import AgentEvent
        assert isinstance(result, AgentEvent)
        assert result.type == EventType.ERROR

    def test_process_delegation_results_fallback_tool_errors(self) -> None:
        """Line 590: fallback to _delegation_tool_errors attr."""
        from henchman.agents.delegation import DelegationRunner
        from henchman.config.schema import Settings
        from henchman.providers.base import Message

        runner = DelegationRunner(
            pool=MagicMock(),
            settings=Settings(),
            shared_context=[],
            metrics=MagicMock(),
            run_agent_loop=AsyncMock(),
            assess_completion=MagicMock(),
        )

        mock_agent = MagicMock(spec=[])  # no get_delegation_errors
        mock_agent._delegation_tool_errors = ["error 1", "error 2"]
        mock_agent.messages = [Message(role="assistant", content="done")]
        mock_agent_completion = MagicMock()
        mock_agent_completion.return_value = MagicMock()
        runner._assess_completion = MagicMock()
        runner._assess_completion.return_value = MagicMock()

        with patch.object(
            runner,
            "_assess_completion",
            return_value=MagicMock(value="COMPLETED"),
        ):
            summary, parsed, status = runner._process_delegation_results(
                "explorer", mock_agent, 0
            )
        assert "TOOL ERRORS" in summary or "error 1" in summary


# ---------------------------------------------------------------------------
# orchestrator_execution.py – missing lines 76-77, 87-89, 102-104
# ---------------------------------------------------------------------------


class TestOrchestratorExecutionMissingLines:
    """Cover missing paths in orchestrator_execution.py."""

    @pytest.mark.anyio
    async def test_run_agent_loop_none_agent(self) -> None:
        """Lines 76-77: raises ValueError when params.agent is None."""
        from henchman.agents.orchestrator_execution import ExecutionController
        from henchman.agents.orchestrator_types import AgentLoopParams

        orchestrator = MagicMock()
        orchestrator.validator = MagicMock()
        orchestrator.validator.check_thinking_pattern.return_value = None
        orchestrator.validator.check_stall_failure.return_value = None

        controller = ExecutionController(orchestrator=orchestrator)
        params = AgentLoopParams(agent=None, input_text="test", depth=0)

        with pytest.raises(ValueError, match="Agent must be provided"):
            async for _ in controller.run_agent_loop(params):
                pass

    @pytest.mark.anyio
    async def test_run_agent_loop_generator_exhausted_no_pending(self) -> None:
        """Lines 102-103: break when generator exhausted and no new generator."""
        from henchman.agents.orchestrator_execution import ExecutionController
        from henchman.agents.orchestrator_types import AgentLoopParams
        from henchman.core.events import AgentEvent, EventType

        orchestrator = MagicMock()
        orchestrator.validator = MagicMock()
        orchestrator.validator.check_thinking_pattern.return_value = None
        orchestrator.validator.check_stall_failure.return_value = None

        controller = ExecutionController(orchestrator=orchestrator)

        mock_agent = MagicMock()

        async def simple_gen():
            yield AgentEvent(EventType.CONTENT, "hello")

        mock_agent.run.return_value = simple_gen()

        params = AgentLoopParams(agent=mock_agent, input_text="test", depth=0)

        with patch("henchman.agents.orchestrator_execution.check_colon_stall", return_value=None):
            with patch("henchman.agents.orchestrator_execution.finalize_loop"):
                events = []
                async for e in controller.run_agent_loop(params):
                    events.append(e)

        assert any(e.type == EventType.CONTENT for e in events)

    def test_process_no_pending_with_stall_event(self) -> None:
        """Lines 87-89: _process_no_pending includes stall event."""
        from henchman.agents.orchestrator_execution import ExecutionController
        from henchman.agents.orchestrator_types import LoopState
        from henchman.core.events import AgentEvent, EventType

        orchestrator = MagicMock()
        stall_event = AgentEvent(EventType.ERROR, "stalled")
        orchestrator.validator.check_thinking_pattern.return_value = None
        orchestrator.validator.check_stall_failure.return_value = stall_event

        controller = ExecutionController(orchestrator=orchestrator)
        agent = MagicMock()
        state = LoopState()

        with patch("henchman.agents.orchestrator_execution.check_colon_stall", return_value=None):
            should_break, events, new_gen = controller._process_no_pending(agent, state)

        assert stall_event in events

    def test_process_no_pending_validator_none(self) -> None:
        """Lines 129-134: _process_no_pending raises when validator is None."""
        from henchman.agents.orchestrator_execution import ExecutionController
        from henchman.agents.orchestrator_types import LoopState

        orchestrator = MagicMock()
        orchestrator.validator = None

        controller = ExecutionController(orchestrator=orchestrator)
        agent = MagicMock()
        state = LoopState()

        with pytest.raises(RuntimeError, match="validator is None"):
            controller._process_no_pending(agent, state)


# ---------------------------------------------------------------------------
# orchestrator_init.py – missing lines 69->71, 112-113
# ---------------------------------------------------------------------------


class TestOrchestratorInitMissingLines:
    """Cover missing paths in orchestrator_init.py."""

    def test_init_orchestrator_with_none_config(self) -> None:
        """Lines 69->71: init_orchestrator creates OrchestratorConfig when config=None."""
        from henchman.agents.orchestrator_init import init_orchestrator

        orchestrator = MagicMock()
        provider = MagicMock()
        provider.name = "mock"

        with patch("henchman.agents.orchestrator_init._init_core"):
            with patch("henchman.agents.orchestrator_init._init_agents"):
                init_orchestrator(orchestrator, provider, config=None)

    def test_init_agents_with_custom_agent_configs(self) -> None:
        """Lines 112-113: _init_agents merges custom agent configs from settings."""
        from henchman.agents.config import AgentConfig
        from henchman.agents.orchestrator_init import OrchestratorConfig, _init_agents

        orchestrator = MagicMock()
        # Simulate settings.agents.agents having custom entries
        mock_settings = MagicMock()
        custom_config = MagicMock(spec=AgentConfig)
        mock_settings.agents.agents = {"custom_role": custom_config}
        mock_settings.context.intelligent_context = False
        mock_settings.context.importance_threshold = 0.5
        mock_settings.context.cluster_similarity_threshold = 0.7
        mock_settings.context.adaptive_compression = True
        orchestrator.settings = mock_settings

        provider = MagicMock()
        config = OrchestratorConfig()

        with patch("henchman.agents.orchestrator_init.get_default_team", return_value={}):
            with patch("henchman.agents.orchestrator_init._create_pool"):
                with patch("henchman.agents.orchestrator_init.setup_tech_lead"):
                    with patch(
                        "henchman.agents.orchestrator_init.DelegationRunner"
                    ) as mock_dr:
                        mock_dr.return_value = MagicMock()
                        _init_agents(orchestrator, provider, config)


# ---------------------------------------------------------------------------
# orchestrator_anchoring.py – missing lines 126-131
# ---------------------------------------------------------------------------


class TestOrchestratorAnchoringMissingLines:
    """Cover paths in orchestrator_anchoring.py."""

    def test_is_truthy_failure_none_is_false(self) -> None:
        """None is treated as no failure."""
        from henchman.agents.orchestrator_anchoring import _is_truthy_failure

        assert _is_truthy_failure(None) is False

    def test_is_truthy_failure_true_is_true(self) -> None:
        """Boolean True indicates a stall failure."""
        from henchman.agents.orchestrator_anchoring import _is_truthy_failure

        assert _is_truthy_failure(True) is True

    def test_is_truthy_failure_false_is_false(self) -> None:
        """Boolean False indicates no failure."""
        from henchman.agents.orchestrator_anchoring import _is_truthy_failure

        assert _is_truthy_failure(False) is False

    def test_is_truthy_failure_truthy_string(self) -> None:
        """Non-empty string is truthy → failure."""
        from henchman.agents.orchestrator_anchoring import _is_truthy_failure

        assert _is_truthy_failure("stall") is True

    def test_is_truthy_failure_empty_string(self) -> None:
        """Empty string is falsy → no failure."""
        from henchman.agents.orchestrator_anchoring import _is_truthy_failure

        assert _is_truthy_failure("") is False


# ---------------------------------------------------------------------------
# orchestrator_events.py – missing line 111
# ---------------------------------------------------------------------------


class TestOrchestratorEventsMissingLines:
    """Cover missing paths in orchestrator_events.py."""

    def test_update_ledger_no_ledger(self) -> None:
        """Line 110->exit: update_ledger skips when ledger is None."""
        from henchman.agents.orchestrator_events import update_ledger

        # Should be a no-op when ledger=None
        update_ledger(None, None, "result", had_error=False)

    def test_update_ledger_had_error(self) -> None:
        """Line 111: update_ledger calls fail_delegation."""
        from henchman.agents.orchestrator_events import update_ledger

        mock_ledger = MagicMock()
        mock_record = MagicMock()

        update_ledger(mock_ledger, mock_record, "result", had_error=True)
        mock_ledger.fail_delegation.assert_called_once_with(mock_record, "result")

    def test_update_ledger_no_error(self) -> None:
        """Line 118: update_ledger calls complete_delegation when had_error=False."""
        from henchman.agents.orchestrator_events import update_ledger

        mock_ledger = MagicMock()
        mock_record = MagicMock()

        update_ledger(mock_ledger, mock_record, "result", had_error=False)
        mock_ledger.complete_delegation.assert_called_once_with(mock_record, "result")

    def test_update_ledger_no_record(self) -> None:
        """Line 114: update_ledger returns early when record is None."""
        from henchman.agents.orchestrator_events import update_ledger

        mock_ledger = MagicMock()
        update_ledger(mock_ledger, None, "result", had_error=False)
        mock_ledger.complete_delegation.assert_not_called()


# ---------------------------------------------------------------------------
# orchestrator.py – missing lines 140, 144, 153
# ---------------------------------------------------------------------------


class TestOrchestratorMissingLines:
    """Cover missing paths in orchestrator.py."""

    def test_get_pool(self) -> None:
        """Line 140: Orchestrator.get_pool() returns pool."""
        from henchman.agents.orchestrator import Orchestrator

        provider = MagicMock()
        provider.name = "mock"
        orch = Orchestrator(default_provider=provider)
        pool = orch.get_pool()
        assert pool is orch.pool

    def test_get_event_bus(self) -> None:
        """Line 144: Orchestrator.get_event_bus() returns event_bus."""
        from henchman.agents.orchestrator import Orchestrator

        provider = MagicMock()
        provider.name = "mock"
        orch = Orchestrator(default_provider=provider)
        bus = orch.get_event_bus()
        assert bus is orch.event_bus

    def test_delegation_runner_property(self) -> None:
        """Line 153: _delegation_runner property returns delegation_runner."""
        from henchman.agents.orchestrator import Orchestrator

        provider = MagicMock()
        provider.name = "mock"
        orch = Orchestrator(default_provider=provider)
        assert orch._delegation_runner is orch.delegation_runner


# ---------------------------------------------------------------------------
# orchestrator_loop.py – missing lines 111, 216
# ---------------------------------------------------------------------------


class TestOrchestratorLoopMissingLines:
    """Cover missing paths in orchestrator_loop.py."""

    @pytest.mark.anyio
    async def test_collect_events_stop_async_iteration(self) -> None:
        """Line 111: collect_events handles StopAsyncIteration from generator."""
        from henchman.agents.orchestrator_loop import collect_events

        # Create a mock async iterator that raises StopAsyncIteration on __anext__
        class StopIterGenerator:
            def __aiter__(self):
                return self

            async def __anext__(self):
                raise StopAsyncIteration

        pending: list = []
        # The collect_events generator should handle this gracefully
        events = []
        try:
            async for event in collect_events(StopIterGenerator(), pending):
                events.append(event)
        except (StopAsyncIteration, RuntimeError):
            # Expected - generator exhausted or Python 3.7+ RuntimeError
            pass
        # No events should have been collected
        assert len(events) == 0

    def test_check_colon_stall_non_string_content(self) -> None:
        """Line 216: check_colon_stall handles non-string content."""
        from henchman.agents.orchestrator_loop import check_colon_stall
        from henchman.providers.base import Message

        agent = MagicMock()
        # Make last message have non-string content
        agent.messages = [Message(role="assistant", content=None)]

        result = check_colon_stall(agent, retries=0)
        # Should handle gracefully
        assert result is None or isinstance(result, tuple)


# ---------------------------------------------------------------------------
# orchestrator_components.py – missing line 62
# ---------------------------------------------------------------------------


class TestOrchestratorComponentsMissingLines:
    """Cover missing paths in orchestrator_components.py."""

    def test_check_thinking_pattern_stripped_no_thinking(self) -> None:
        """Line 61: check_thinking_pattern calls handle_missing_thinking."""
        from henchman.agents.orchestrator_components import AgentValidator
        from henchman.providers.base import Message

        orchestrator = MagicMock()
        orchestrator.metrics = MagicMock()
        orchestrator.settings.agents.thinking_required = True

        validator = AgentValidator(orchestrator=orchestrator)

        agent = MagicMock()
        agent.messages = [Message(role="assistant", content="No thinking here")]

        with patch(
            "henchman.agents.orchestrator_components.should_check_thinking", return_value=True
        ), patch(
            "henchman.agents.orchestrator_components.handle_missing_thinking"
        ) as mock_missing:
            mock_missing.return_value = MagicMock()
            result = validator.check_thinking_pattern(agent)
        mock_missing.assert_called_once()

    def test_check_thinking_pattern_empty_content(self) -> None:
        """Line 62: check_thinking_pattern returns None when content is empty."""
        from henchman.agents.orchestrator_components import AgentValidator
        from henchman.providers.base import Message

        orchestrator = MagicMock()
        orchestrator.metrics = MagicMock()

        validator = AgentValidator(orchestrator=orchestrator)

        agent = MagicMock()
        # content is empty/whitespace - stripped is falsy
        agent.messages = [Message(role="assistant", content="")]

        with patch(
            "henchman.agents.orchestrator_components.should_check_thinking", return_value=True
        ):
            result = validator.check_thinking_pattern(agent)
        assert result is None


# ---------------------------------------------------------------------------
# presets.py – missing lines 71, 75->77, 79->81
# ---------------------------------------------------------------------------


class TestPresetsMissingLines:
    """Cover missing paths in presets.py."""

    def test_create_agent_config_default_tool_categories(self) -> None:
        """Line 71: _create_agent_config uses default ToolCategoryConfig when None."""
        from henchman.agents.presets import _create_agent_config

        config = _create_agent_config(
            name="TestAgent",
            role="test",
            description="A test agent",
            tool_categories=None,
        )
        assert config is not None
        assert config.name == "TestAgent"

    def test_create_agent_config_no_file_edit_tools(self) -> None:
        """Lines 75->77: file_edit_tools=False skips those tools."""
        from henchman.agents.presets import ToolCategoryConfig, _create_agent_config

        tc = ToolCategoryConfig(file_edit_tools=False)
        config = _create_agent_config(
            name="ReadOnly",
            role="readonly",
            description="Read-only agent",
            tool_categories=tc,
        )
        # Should not have edit tools
        from henchman.agents.presets import _FILE_EDIT_TOOLS

        for tool in _FILE_EDIT_TOOLS:
            assert tool not in config.tools

    def test_create_agent_config_no_git_tools(self) -> None:
        """Lines 79->81: git_tools=False skips git tools."""
        from henchman.agents.presets import _GIT_TOOLS, ToolCategoryConfig, _create_agent_config

        tc = ToolCategoryConfig(git_tools=False)
        config = _create_agent_config(
            name="NoGit",
            role="nogit",
            description="No git agent",
            tool_categories=tc,
        )
        for tool in _GIT_TOOLS:
            assert tool not in config.tools

    def test_create_agent_config_with_special_tools(self) -> None:
        """Line 89: special_tools are added."""
        from henchman.agents.presets import _create_agent_config

        config = _create_agent_config(
            name="Delegator",
            role="delegator",
            description="Can delegate",
            special_tools=["delegate_task"],
        )
        assert "delegate_task" in config.tools


# ---------------------------------------------------------------------------
# prompts.py – missing lines 586->588, 592
# ---------------------------------------------------------------------------


class TestPromptsMissingLines:
    """Cover missing paths in prompts.py."""

    def test_get_agent_prompt_with_team_descriptions_and_no_desc(self) -> None:
        """Lines 586->588: member with no description falls back to name only."""
        from henchman.agents.prompts import get_agent_prompt

        team_descriptions = {"coder": "A coding specialist"}
        # Explorer has no description in the dict
        prompt = get_agent_prompt(
            role="tech_lead",
            team_members=["Coder (coder)", "Explorer (explorer)"],
            team_descriptions=team_descriptions,
        )
        assert "Coder" in prompt
        assert "Explorer" in prompt

    def test_get_agent_prompt_member_with_no_role_parens(self) -> None:
        """Line 592: member without parens handled gracefully."""
        from henchman.agents.prompts import get_agent_prompt

        prompt = get_agent_prompt(
            role="tech_lead",
            team_members=["SimpleMember"],  # no parens
            team_descriptions={"": "some desc"},
        )
        assert "SimpleMember" in prompt


# ---------------------------------------------------------------------------
# pool.py – missing lines 129-130, 149->157
# ---------------------------------------------------------------------------


class TestPoolMissingLines:
    """Cover missing paths in pool.py."""

    def test_get_agent_with_provider_registry(self) -> None:
        """Lines 129-130: get_agent creates agent with provider from registry."""
        from henchman.agents.config import AgentConfig
        from henchman.agents.pool import AgentPool

        provider = MagicMock()
        provider.name = "mock"
        provider_registry = MagicMock()
        mock_provider_cls = MagicMock()
        mock_provider_cls.return_value = MagicMock()
        provider_registry.get.return_value = mock_provider_cls

        config = AgentConfig(
            name="Explorer",
            role="explorer",
            description="Explores",
            provider="openai",  # Has a specific provider
        )
        pool = AgentPool(
            default_provider=provider,
            configs={"explorer": config},
            parent_tool_registry=MagicMock(),
            provider_registry=provider_registry,
            event_bus=MagicMock(),
        )
        agent = pool.get_agent("explorer")
        assert agent is not None
        provider_registry.get.assert_called_with("openai")

    def test_get_agent_with_custom_system_prompt(self) -> None:
        """Lines 149->157: get_agent uses custom system_prompt from config."""
        from henchman.agents.config import AgentConfig
        from henchman.agents.pool import AgentPool

        provider = MagicMock()
        provider.name = "mock"

        config = AgentConfig(
            name="Custom",
            role="custom",
            description="Custom agent",
            system_prompt="My custom prompt",
        )
        pool = AgentPool(
            default_provider=provider,
            configs={"custom": config},
            parent_tool_registry=MagicMock(),
            provider_registry=None,
            event_bus=MagicMock(),
        )
        agent = pool.get_agent("custom")
        assert agent is not None

    def test_reset_agent_exists(self) -> None:
        """Line 233->exit: reset_agent calls clear_history when role exists."""
        from henchman.agents.config import AgentConfig
        from henchman.agents.pool import AgentPool

        provider = MagicMock()
        provider.name = "mock"

        config = AgentConfig(name="Agent", role="agent", description="An agent")
        pool = AgentPool(
            default_provider=provider,
            configs={"agent": config},
            parent_tool_registry=MagicMock(),
            provider_registry=None,
            event_bus=MagicMock(),
        )
        # Create the agent in pool
        agent = pool.get_agent("agent")
        # Now reset it
        pool.reset_agent("agent")
        # Should not raise

    def test_reset_agent_nonexistent(self) -> None:
        """Line 233->exit: reset_agent skips silently when role not found."""
        from henchman.agents.pool import AgentPool

        provider = MagicMock()
        provider.name = "mock"

        pool = AgentPool(
            default_provider=provider,
            configs={},
            parent_tool_registry=MagicMock(),
            provider_registry=None,
            event_bus=MagicMock(),
        )
        # Should not raise
        pool.reset_agent("nonexistent_role")


# ---------------------------------------------------------------------------
# presets.py - line 75->77 (basic_file_tools=False)
# ---------------------------------------------------------------------------


class TestPresetsMissingLinesExtra:
    """Extra coverage for presets.py missing branches."""

    def test_create_agent_config_no_basic_file_tools(self) -> None:
        """Lines 75->77: _create_agent_config skips basic file tools."""
        from henchman.agents.presets import (
            _BASIC_FILE_TOOLS,
            ToolCategoryConfig,
            _create_agent_config,
        )

        tc = ToolCategoryConfig(basic_file_tools=False)
        config = _create_agent_config(
            name="NoBasicFiles",
            role="nofiles",
            description="No basic file tools",
            tool_categories=tc,
        )
        for tool in _BASIC_FILE_TOOLS:
            assert tool not in config.tools


# ---------------------------------------------------------------------------
# orchestrator_init.py – line 69->71 (config is None)
# ---------------------------------------------------------------------------


class TestOrchestratorInitMissingLinesExtra:
    """Extra coverage for orchestrator_init.py."""

    def test_initialize_orchestrator_with_config(self) -> None:
        """Line 69->71: init_orchestrator uses existing config (false branch)."""
        from henchman.agents.orchestrator_init import OrchestratorConfig, init_orchestrator

        orchestrator = MagicMock()
        mock_settings = MagicMock()
        mock_settings.agents.agents = {}
        orchestrator.settings = mock_settings

        provider = MagicMock()
        config = OrchestratorConfig()  # Non-None config

        with patch("henchman.agents.orchestrator_init._init_core"):
            with patch("henchman.agents.orchestrator_init._init_agents"):
                # config is not None - skips OrchestratorConfig() creation
                init_orchestrator(orchestrator, provider, config=config)

    def test_initialize_orchestrator_without_config(self) -> None:
        """Line 69->71: init_orchestrator creates OrchestratorConfig when config=None."""
        from henchman.agents.orchestrator_init import init_orchestrator

        orchestrator = MagicMock()
        mock_settings = MagicMock()
        mock_settings.agents.agents = {}
        mock_settings.context.intelligent_context = False
        orchestrator.settings = mock_settings

        provider = MagicMock()

        with patch("henchman.agents.orchestrator_init._init_core"):
            with patch("henchman.agents.orchestrator_init._init_agents"):
                # config=None triggers OrchestratorConfig() creation
                init_orchestrator(orchestrator, provider, config=None)


# ---------------------------------------------------------------------------
# orchestrator_loop.py - line 216 (non-string content)
# ---------------------------------------------------------------------------


class TestOrchestratorLoopMissingLinesExtra:
    """Extra coverage for orchestrator_loop.py."""

    def test_check_colon_stall_non_string_content(self) -> None:
        """Line 216: check_colon_stall converts non-string content to string."""
        from henchman.agents.orchestrator_loop import check_colon_stall

        agent = MagicMock()
        # Return non-string content
        with patch(
            "henchman.agents.orchestrator_loop.last_assistant_content",
            return_value=42,  # Non-string content
        ):
            result = check_colon_stall(agent, retries=0)
        # Should convert to str and not stall (since "42" doesn't end with ":")
        assert result is None


# ---------------------------------------------------------------------------
# delegation.py – _process_delegation_results validation paths
# ---------------------------------------------------------------------------


class TestProcessDelegationResultsValidation:
    """Cover validation error paths in DelegationRunner._process_delegation_results."""

    def _make_runner(self) -> DelegationRunner:
        """Create a minimal DelegationRunner."""
        from unittest.mock import AsyncMock, MagicMock

        from henchman.agents.delegation import DelegationRunner
        from henchman.config.schema import Settings

        return DelegationRunner(
            pool=MagicMock(),
            settings=Settings(),
            shared_context=[],
            metrics=MagicMock(),
            run_agent_loop=AsyncMock(),
            assess_completion=MagicMock(),
        )

    def test_msg_start_not_int_raises_type_error(self) -> None:
        """Line 738: raises TypeError when msg_start is not an int."""
        import pytest

        runner = self._make_runner()
        mock_agent = MagicMock()
        with pytest.raises(TypeError, match="msg_start must be an integer"):
            runner._process_delegation_results("role", mock_agent, "zero")  # type: ignore[arg-type]

    def test_msg_start_negative_raises_value_error(self) -> None:
        """Line 743: raises ValueError when msg_start is negative."""
        import pytest

        runner = self._make_runner()
        mock_agent = MagicMock()
        with pytest.raises(ValueError, match="msg_start must be non-negative"):
            runner._process_delegation_results("role", mock_agent, -1)

    def test_agent_missing_messages_attr_raises_attribute_error(self) -> None:
        """Line 749: raises AttributeError when agent lacks messages attr."""
        import pytest

        runner = self._make_runner()
        mock_agent = MagicMock(spec=[])  # no attributes
        with pytest.raises(AttributeError, match="missing 'messages' attribute"):
            runner._process_delegation_results("role", mock_agent, 0)

    def test_messages_none_raises_value_error(self) -> None:
        """Line 755: raises ValueError when agent.messages is None."""
        import pytest

        runner = self._make_runner()
        mock_agent = MagicMock()
        mock_agent.messages = None
        with pytest.raises(ValueError, match="messages is None"):
            runner._process_delegation_results("role", mock_agent, 0)

    def test_messages_not_sequence_raises_type_error(self) -> None:
        """Line 758: raises TypeError when messages is not a Sequence."""
        import pytest

        runner = self._make_runner()
        mock_agent = MagicMock()
        mock_agent.messages = 42  # not a sequence
        with pytest.raises(TypeError, match="must be a Sequence"):
            runner._process_delegation_results("role", mock_agent, 0)

    def test_msg_start_exceeds_length_raises_value_error(self) -> None:
        """Line 764: raises ValueError when msg_start > len(messages)."""
        import pytest

        runner = self._make_runner()
        mock_agent = MagicMock()
        mock_agent.messages = []  # empty list
        with pytest.raises(ValueError, match="exceeds messages length"):
            runner._process_delegation_results("role", mock_agent, 1)

    def test_message_without_role_raises_type_error(self) -> None:
        """Line 775: raises TypeError when message lacks role/content."""
        import pytest

        runner = self._make_runner()
        mock_agent = MagicMock()
        mock_agent.messages = ["not_a_message_object"]  # string has no role
        with pytest.raises(TypeError, match="messages do not appear to be Message instances"):
            runner._process_delegation_results("role", mock_agent, 0)

    def test_empty_messages_skips_validation_block(self) -> None:
        """Branch 770->789: empty messages list skips the message validation block."""
        from unittest.mock import MagicMock, patch

        runner = self._make_runner()
        mock_agent = MagicMock()
        mock_agent.messages = []  # empty, so msg_start (0) == len(0), passes bounds check
        mock_agent.get_delegation_errors = MagicMock(return_value=[])

        with patch.object(runner, "_assess_completion", return_value=MagicMock(value="DONE")):
            summary, parsed, status = runner._process_delegation_results("role", mock_agent, 0)
        assert isinstance(summary, str)
