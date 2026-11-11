"""MCP effective credentials join the runtime's shared evidence policy."""

from types import SimpleNamespace

from henchman.cli.evidence import runtime_evidence_redactor
from henchman.cli.tool_manager import ToolManager
from henchman.config.schema import McpServerConfig, Settings
from henchman.mcp.auth import McpAuthService
from henchman.mcp.manager import McpManager
from henchman.utils.evidence_redaction import EvidenceRedactor


def test_manager_replays_historical_auth_into_late_evidence_binding():
    manager = McpManager({"fixture": McpServerConfig(command="unused")})
    manager.set_auth_token("fixture", "old-private-auth-canary")
    manager.set_auth_token("fixture", "new-private-auth-canary")
    manager.clear_auth_token("fixture")
    policy = EvidenceRedactor()
    manager.register_evidence(policy)
    assert "auth-canary" not in policy.text("old-private-auth-canary new-private-auth-canary")


def test_bound_policy_tracks_reference_rotation_even_for_ordinary_named_fields(monkeypatch):
    monkeypatch.setenv("ORDINARY_SOURCE", "initial-reference-private-canary")
    manager = McpManager({"fixture": McpServerConfig(command="unused", env={"PLAIN": "${ORDINARY_SOURCE}"})})
    policy = EvidenceRedactor()
    manager.register_evidence(policy)
    monkeypatch.setenv("ORDINARY_SOURCE", "replacement-reference-private-canary")
    text = policy.text("initial-reference-private-canary replacement-reference-private-canary")
    assert "private-canary" not in text
    assert manager.configs["fixture"].env == {"PLAIN": "${ORDINARY_SOURCE}"}


def test_runtime_helper_binds_restored_auth_and_registers_later_rotation(tmp_path):
    McpAuthService(tmp_path).set_token("fixture", "restored-runtime-private-canary")
    settings = Settings(mcp_servers={"fixture": McpServerConfig(command="unused")})
    manager = McpManager.create_from_settings(settings, project_root=tmp_path)
    assert manager is not None
    policy = EvidenceRedactor()
    runtime = SimpleNamespace(settings=settings, core_context=SimpleNamespace(
        mcp_manager=manager, session_manager=SimpleNamespace(session_manager=SimpleNamespace(evidence_redactor=policy)),
    ))
    assert runtime_evidence_redactor(runtime) is policy
    manager.set_auth_token("fixture", "rotated-runtime-private-canary")
    assert "private-canary" not in policy.text("restored-runtime-private-canary rotated-runtime-private-canary")


def test_tool_runtime_binding_registers_credentials_before_display_or_tool_execution(tmp_path):
    from henchman.core.session import SessionManager, SessionMessage

    manager = McpManager({"fixture": McpServerConfig(command="unused")})
    manager.set_auth_token("fixture", "persistence-private-canary")
    core = SessionManager(data_dir=tmp_path / "sessions")
    policy = core.evidence_redactor
    session_manager = SimpleNamespace(session_manager=core)
    tools = ToolManager()
    tools.bind_runtime(project_root=tmp_path, session_manager=session_manager, mcp_manager=manager)
    assert "persistence-private-canary" not in policy.text("persistence-private-canary")
    manager.set_auth_token("fixture", "next-persistence-private-canary")
    assert "next-persistence-private-canary" not in policy.text("next-persistence-private-canary")
    session = core.create_session("fixture-project")
    raw = "persistence-private-canary next-persistence-private-canary"
    session.messages.append(SessionMessage(role="tool", content=raw))
    destination = core.save(session)
    assert "private-canary" not in destination.read_text(encoding="utf-8")
    assert session.messages[0].content == raw
