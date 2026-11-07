"""Prompt history persists evidence while retaining live editable input."""

from unittest.mock import MagicMock, patch

from henchman.cli.input import create_session
from henchman.cli.input_handler import InputHandler
from henchman.utils.evidence_redaction import EvidenceRedactor


def test_prompt_history_masks_disk_copy_and_keeps_live_input(tmp_path, monkeypatch):
    monkeypatch.setenv("HENCHMAN_TEST_TOKEN", "environment-canary")
    path = tmp_path / "history"
    with patch("henchman.cli.input.PromptSession") as prompt:
        create_session(path)
    history = prompt.call_args.kwargs["history"]
    raw = "echo environment-canary\nAuthorization: unrelated-canary"
    history.append_string(raw)
    assert history.get_strings() == [raw]
    saved = path.read_text()
    assert "canary" not in saved
    assert "+echo [REDACTED]" in saved
    assert "+Authorization: [REDACTED]" in saved


def test_input_handler_uses_shared_policy_through_rotation(tmp_path):
    path = tmp_path / "history"
    policy = EvidenceRedactor(["initial-canary"])
    handler = InputHandler(MagicMock(), MagicMock(), path, evidence_redactor=policy)
    with patch("henchman.cli.input.PromptSession") as prompt:
        handler.initialize_prompt_session()
    history = prompt.call_args.kwargs["history"]
    history.append_string("initial-canary")
    policy.register_secret("rotated-canary")
    history.append_string("initial-canary rotated-canary")
    assert "canary" not in path.read_text()
    assert history.get_strings() == ["initial-canary", "initial-canary rotated-canary"]
