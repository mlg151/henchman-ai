"""Authentication commands stay transient before accepted echo and recall history."""

import asyncio

import pytest
from prompt_toolkit.application import create_app_session
from prompt_toolkit.input import create_pipe_input
from prompt_toolkit.output import DummyOutput

from henchman.cli.input import EvidenceFileHistory, create_session
from henchman.utils.evidence_redaction import EvidenceRedactor


@pytest.mark.parametrize("raw", ["/mcp auth login fixture", "/mcp auth login fixture https://private.invalid/code-canary",
                                "/mcp connect https://private.invalid/token-canary", "/MCP AUTH bad private-canary"])
def test_auth_candidates_are_omitted_from_prompt_history(tmp_path, raw):
    history = EvidenceFileHistory(str(tmp_path / "history"), EvidenceRedactor())
    history.append_string(raw)
    assert history.get_strings() == []
    assert not (tmp_path / "history").exists()
    history.append_string("ordinary draft")
    assert history.get_strings() == ["ordinary draft"]


async def test_actual_prompt_acceptance_retains_transient_input_without_echo_or_history(tmp_path):
    raw = "/mcp auth login fixture https://private.invalid/code-canary"
    with create_pipe_input() as pipe, create_app_session(input=pipe, output=DummyOutput()):
        session = create_session(tmp_path / "history")
        task = asyncio.create_task(session.prompt_async("> "))
        pipe.send_text(raw + "\n")
        assert await asyncio.wait_for(task, 3) == raw
        assert "canary" not in session.default_buffer.text
        assert session.history.get_strings() == []
        assert not (tmp_path / "history").exists()


def test_older_prompt_history_auth_entries_are_not_recalled(tmp_path):
    from prompt_toolkit.history import FileHistory

    path = tmp_path / "history"
    older = FileHistory(str(path))
    older.append_string("/mcp auth login fixture https://private.invalid/code-canary")
    older.append_string("ordinary draft")
    before = path.read_bytes()
    history = EvidenceFileHistory(str(path), EvidenceRedactor())
    assert list(history.load_history_strings()) == ["ordinary draft"]
    assert path.read_bytes() == before  # Filtering recall does not erase previous host evidence.
