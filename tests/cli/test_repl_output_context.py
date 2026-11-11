import io
from unittest.mock import AsyncMock, Mock, patch

import pytest
from prompt_toolkit.application import create_app_session
from rich.console import Console

from henchman.cli.repl import Repl, ReplConfig
from tests.cli.test_repl import MockProvider


@pytest.mark.anyio
async def test_repl_run_reuses_prompt_output(tmp_path, monkeypatch):
    """The stdout proxy reuses the output already selected for the prompt."""
    # Setup
    console = Console(file=io.StringIO())
    provider = MockProvider()
    config = ReplConfig(auto_save=False, history_file=tmp_path / "history")

    monkeypatch.chdir(tmp_path)

    repl = Repl(provider=provider, console=console, config=config)

    # Mocks
    repl.initialize_mcp = AsyncMock()
    repl.output_handler.start_background_indexing = Mock()
    repl._get_input = AsyncMock(return_value="/quit")

    with (
        create_app_session(output=None),
        patch(
            "prompt_toolkit.output.defaults.create_output",
            side_effect=AssertionError("unexpected output factory"),
        ),
    ):
        await repl.run()
