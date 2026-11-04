import io
from unittest.mock import MagicMock, patch

from henchman.cli.input import PlainTextOutput, create_session


class MockNonTTYStream(io.StringIO):
    def isatty(self) -> bool:
        return False


def test_non_tty_stdout_uses_plain_text_output(monkeypatch):
    mock_stream = MockNonTTYStream()
    monkeypatch.setattr("sys.stdout", mock_stream)
    with patch("henchman.cli.input.PromptSession") as mock_prompt_session:
        create_session()
        _, kwargs = mock_prompt_session.call_args
        assert kwargs["output"] is not None
        assert isinstance(kwargs["output"], PlainTextOutput)
        assert kwargs["output"].stdout is mock_stream


def test_tty_stdout_preserves_none_output(monkeypatch):
    mock_stream = MagicMock()
    mock_stream.isatty.return_value = True
    monkeypatch.setattr("sys.stdout", mock_stream)
    with patch("henchman.cli.input.PromptSession") as mock_prompt_session:
        create_session()
        _, kwargs = mock_prompt_session.call_args
        assert kwargs["output"] is None


def test_none_stdout_preserves_none_output(monkeypatch):
    monkeypatch.setattr("sys.stdout", None)
    with patch("henchman.cli.input.PromptSession") as mock_prompt_session:
        create_session()
        _, kwargs = mock_prompt_session.call_args
        assert kwargs["output"] is None
