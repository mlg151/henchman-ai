"""Tests for plan-mode transition authority (#18).

Plan mode has two distinct authorities:

* **User-imposed boundary** — the user (via ``/plan`` or an authorized
  runtime transition) imposes a read-only boundary.  A model-callable
  ``exit_plan_mode`` must NOT be able to lift it.
* **Model-proposed planning** — the model can enter and exit its own
  planning mode.  ``exit_plan_mode`` widens execution rights only for
  transitions the model itself opened.

``Session.plan_mode_origin`` records which authority opened the current
plan mode so persisted sessions keep the distinction across resumes.
"""

from __future__ import annotations

from henchman.core.session_data import (
    Session,
    session_from_dict,
)
from henchman.tools.base import ConfirmationRequest, Tool, ToolKind, ToolResult
from henchman.tools.builtins.tier2_tools import (
    EnterPlanModeTool,
    ExitPlanModeTool,
)
from henchman.tools.registry import ToolRegistry


async def _approve(request: ConfirmationRequest) -> bool:  # noqa: ARG001
    return True


def _make_session(
    *,
    plan_mode: bool = False,
    origin: str = "user",
) -> Session:
    session = Session(
        id="sess-1",
        project_hash="proj",
        started="2026-01-01T00:00:00Z",
        last_updated="2026-01-01T00:00:00Z",
    )
    session.plan_mode = plan_mode
    session.plan_mode_origin = origin
    return session


class _FakeSessionManager:
    """Minimal session manager binding surface for plan-mode tools."""

    def __init__(self, session: Session | None) -> None:
        self.current = session
        self.saved: list[Session] = []

    def save(self, session: Session) -> None:
        self.saved.append(session)


class _MockWriteTool(Tool):
    @property
    def name(self) -> str:
        return "write_file"

    @property
    def description(self) -> str:
        return "Write to a file"

    @property
    def parameters(self) -> dict:
        return {"type": "object", "properties": {"path": {"type": "string"}}}

    @property
    def kind(self) -> ToolKind:
        return ToolKind.WRITE

    async def execute(self, **params: object) -> ToolResult:
        return ToolResult(content="Executed write_file")


def _registry_with_write_tool() -> ToolRegistry:
    registry = ToolRegistry()
    registry.register(_MockWriteTool())
    registry.set_confirmation_handler(_approve)
    return registry


class TestPlanModeOriginPersistence:
    """plan_mode_origin must survive session persistence round-trips."""

    def test_model_origin_roundtrips(self) -> None:
        session = _make_session(plan_mode=True, origin="model")
        restored = session_from_dict(session.to_dict())
        assert restored.plan_mode is True
        assert restored.plan_mode_origin == "model"

    def test_user_origin_roundtrips(self) -> None:
        session = _make_session(plan_mode=True, origin="user")
        restored = session_from_dict(session.to_dict())
        assert restored.plan_mode is True
        assert restored.plan_mode_origin == "user"

    def test_legacy_session_without_origin_defaults_to_user(self) -> None:
        """Sessions persisted before this field existed stay user-locked."""
        data = _make_session(plan_mode=True).to_dict()
        data.pop("plan_mode_origin", None)
        restored = session_from_dict(data)
        assert restored.plan_mode is True
        assert restored.plan_mode_origin == "user"


class TestModelPlanModeTransitions:
    """The model may open and close its own planning, nothing more."""

    async def test_model_enter_marks_model_origin(self) -> None:
        session = _make_session(plan_mode=False)
        registry = _registry_with_write_tool()
        manager = _FakeSessionManager(session)

        tool = EnterPlanModeTool()
        tool.bind_runtime(tool_registry=registry, session_manager=manager)

        result = await tool.execute()
        assert result.success is True
        assert session.plan_mode is True
        assert session.plan_mode_origin == "model"

    async def test_model_exit_clears_model_proposed_planning(self) -> None:
        session = _make_session(plan_mode=True, origin="model")
        registry = _registry_with_write_tool()
        registry.set_plan_mode(enabled=True)
        manager = _FakeSessionManager(session)

        tool = ExitPlanModeTool()
        tool.bind_runtime(tool_registry=registry, session_manager=manager)

        result = await tool.execute()
        assert result.success is True
        assert session.plan_mode is False
        write = await registry.execute("write_file", {"path": "/tmp/x"})
        assert write.success is True

    async def test_model_exit_cannot_lift_user_imposed_boundary(self) -> None:
        session = _make_session(plan_mode=True, origin="user")
        registry = _registry_with_write_tool()
        registry.set_plan_mode(enabled=True)
        manager = _FakeSessionManager(session)

        tool = ExitPlanModeTool()
        tool.bind_runtime(tool_registry=registry, session_manager=manager)

        result = await tool.execute()
        assert result.success is False
        # The boundary itself must remain in force: session, registry,
        # and effective tool authorization all stay read-only.
        assert session.plan_mode is True
        assert session.plan_mode_origin == "user"
        write = await registry.execute("write_file", {"path": "/tmp/x"})
        assert write.success is False
        assert "Plan Mode" in write.content

    async def test_model_enter_cannot_demote_active_user_boundary(self) -> None:
        session = _make_session(plan_mode=True, origin="user")
        registry = _registry_with_write_tool()
        manager = _FakeSessionManager(session)

        tool = EnterPlanModeTool()
        tool.bind_runtime(tool_registry=registry, session_manager=manager)

        result = await tool.execute()
        assert result.success is True
        # Entering an already-active user boundary must not hand the
        # model the right to exit it.
        assert session.plan_mode is True
        assert session.plan_mode_origin == "user"


class TestUserPlanModeTransitions:
    """Authorized user/runtime transitions may always widen execution rights."""

    async def test_user_exit_lifts_user_imposed_boundary(self) -> None:
        from henchman.cli.commands.plan import apply_plan_mode

        session = _make_session(plan_mode=True, origin="user")
        registry = _registry_with_write_tool()
        registry.set_plan_mode(enabled=True)

        applied = apply_plan_mode(
            enabled=False,
            session=session,
            tool_registry=registry,
            origin="user",
        )
        assert applied is False
        assert session.plan_mode is False
        write = await registry.execute("write_file", {"path": "/tmp/x"})
        assert write.success is True

    async def test_user_exit_lifts_model_proposed_planning(self) -> None:
        from henchman.cli.commands.plan import apply_plan_mode

        session = _make_session(plan_mode=True, origin="model")
        registry = _registry_with_write_tool()
        registry.set_plan_mode(enabled=True)

        applied = apply_plan_mode(
            enabled=False,
            session=session,
            tool_registry=registry,
            origin="user",
        )
        assert applied is False
        assert session.plan_mode is False
        write = await registry.execute("write_file", {"path": "/tmp/x"})
        assert write.success is True

    async def test_user_enter_marks_user_origin(self) -> None:
        from henchman.cli.commands.plan import apply_plan_mode

        session = _make_session(plan_mode=False)
        registry = _registry_with_write_tool()

        applied = apply_plan_mode(
            enabled=True,
            session=session,
            tool_registry=registry,
            origin="user",
        )
        assert applied is True
        assert session.plan_mode is True
        assert session.plan_mode_origin == "user"
