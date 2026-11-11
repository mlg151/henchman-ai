"""Direct Textual displays share the session policy without rewriting execution."""

import asyncio
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from henchman.cli.evidence import runtime_evidence_redactor
from henchman.cli.textual_app import HenchmanTextualApp
from henchman.cli.textual_config import TextualConfig
from henchman.cli.textual_widgets import ChatPane, StatusBar
from henchman.config.schema import Settings


@pytest.fixture
def app(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    provider = MagicMock()
    provider.name = "test"
    provider.api_key = "private-canary"
    return HenchmanTextualApp(
        provider=provider, settings=Settings(),
        config=TextualConfig(auto_save=False, history_file=tmp_path / "history"),
    )


@pytest.mark.parametrize("role", ["user", "assistant", "system", "role-private-canary"])
def test_public_messages_mask_content_and_arbitrary_roles(app, role):
    chat = MagicMock()
    app.query_one = MagicMock(return_value=chat)
    app.add_message(role, "private-canary")
    shown = str(chat.method_calls)
    assert "private-canary" not in shown
    assert "REDACTED" in shown


async def test_context_file_display_masks_content_but_preserves_file(app, tmp_path):
    path = tmp_path / "private-canary.txt"
    raw = "Authorization: Bearer unrelated-canary\nprivate-canary\n"
    path.write_text(raw)
    chat = MagicMock()
    app.query_one = MagicMock(return_value=chat)
    await app._load_and_show_file(path)
    shown = str(chat.method_calls)
    assert "canary" not in shown
    assert "REDACTED" in shown
    assert path.read_text() == raw


async def test_context_preview_redacts_before_truncation(app, tmp_path):
    path = tmp_path / "context.txt"
    path.write_text("x" * 4993 + "private-canary")
    chat = MagicMock()
    app.query_one = MagicMock(return_value=chat)
    await app._load_and_show_file(path)
    shown = str(chat.method_calls)
    assert "private" not in shown


def test_direct_errors_and_fallback_logs_mask_credentials(app, caplog):
    chat = MagicMock()
    app.query_one = MagicMock(return_value=chat)
    error = RuntimeError("failed private-canary")
    app._show_provider_error(error)
    app._handle_file_read_error(chat, error, Path("private-canary"))
    assert "private-canary" not in str(chat.method_calls)
    assert "REDACTED" in str(chat.method_calls)
    app.query_one = MagicMock(side_effect=LookupError)
    app._show_provider_error(error)
    assert "private-canary" not in caplog.text
    assert "RuntimeError: failed [REDACTED]" in caplog.text


def test_unknown_auth_headers_are_redacted_before_display_prefixes(app):
    chat = MagicMock()
    app.query_one = MagicMock(return_value=chat)
    app.notify = MagicMock()
    app._dispatch_to_chat(chat, "custom", "Authorization: header-display-canary")
    error = RuntimeError("Authorization: header-error-canary")
    app._handle_file_read_error(chat, error, Path("ordinary"))
    message = app._show_workspace_error("tasks", ValueError("Authorization: header-workspace-canary"))
    shown = str(chat.method_calls) + str(app.notify.call_args_list) + message
    assert "canary" not in shown
    assert "REDACTED" in shown
    assert str(error) == "Authorization: header-error-canary"


def test_history_projection_and_failure_logs_preserve_live_entry(app, tmp_path, caplog):
    history = tmp_path / "history"
    app.input_handler = SimpleNamespace(history_file=history)
    raw = "echo private-canary"
    app.command_history = [raw]
    app._persist_history_entry(raw)
    assert history.read_text() == "echo [REDACTED]\n"
    assert app.command_history == [raw]
    app.input_handler.history_file = tmp_path / "private-canary" / "missing"
    chat = MagicMock()
    app.query_one = MagicMock(return_value=chat)
    app._persist_history_entry(raw)
    assert "private-canary" not in caplog.text + str(chat.method_calls)
    assert "REDACTED" in caplog.text


def test_status_provider_labels_and_search_use_safe_display_copies(app):
    bar = MagicMock()
    app.query_one = MagicMock(return_value=bar)
    app.update_status("private-canary", tokens=7)
    assert bar.status_text == "[REDACTED]"
    assert bar.tokens == 7
    app._search_mode = True
    app._search_query = "private-canary"
    app._search_matches = []
    app._update_search_status()
    assert "private-canary" not in bar.status_text
    assert app._search_query == "private-canary"
    app.provider.name = "provider-private-canary"
    assert "private-canary" not in app._build_status_text()
    app._announce_provider_switch("private-canary", "new-private-canary")
    assert "private-canary" not in app.sub_title + str(bar.method_calls)


@pytest.mark.parametrize("fail", [False, True])
def test_export_status_and_artifact_share_runtime_policy(app, tmp_path, monkeypatch, fail):
    folder = tmp_path / "private-canary"
    folder.mkdir()
    monkeypatch.chdir(folder)
    chat = MagicMock()
    app.query_one = MagicMock(return_value=chat)
    app.notify = MagicMock()
    session = SimpleNamespace(id="session")
    app.core_context = SimpleNamespace(session_manager=SimpleNamespace(current=session))
    export = MagicMock(return_value="private-canary")
    if fail:
        export.side_effect = ValueError("private-canary")
    monkeypatch.setattr("henchman.cli.textual_mixins.export_as_markdown", export)
    app._handle_export_result("markdown")
    assert "private-canary" not in str(chat.method_calls) + str(app.notify.call_args_list)
    if not fail:
        assert (folder / "session_session.md").read_text() == "[REDACTED]"
    assert session.id == "session"


async def test_input_and_exception_display_preserve_raw_routed_input(app, monkeypatch):
    seen = []
    async with app.run_test(size=(100, 40)):
        chat = app.query_one("#chat-pane", ChatPane)
        user = MagicMock(wraps=chat.add_user_message)
        error = MagicMock(wraps=chat.add_error_message)
        monkeypatch.setattr(chat, "add_user_message", user)
        monkeypatch.setattr(chat, "add_error_message", error)

        async def route(text, _chat):
            seen.append(text)
            failure = RuntimeError("failed private-canary")
            failure.add_note("note private-canary")
            raise failure

        monkeypatch.setattr(app, "_route_input", route)
        worker = app.process_user_input("echo private-canary")
        await asyncio.wait_for(worker.wait(), 3)
        assert seen == ["echo private-canary"]
        assert user.call_args.args[0] == "echo [REDACTED]"
        assert "private-canary" not in error.call_args.args[0]
        assert "RuntimeError" in error.call_args.args[0]
        assert "note [REDACTED]" in error.call_args.args[0]
        assert "private-canary" not in app.query_one("#status-bar", StatusBar).status_text
        assert runtime_evidence_redactor(app).text(seen[0]) == "echo [REDACTED]"
