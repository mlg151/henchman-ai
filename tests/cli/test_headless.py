import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from click.testing import CliRunner
from henchman.cli.app import main

def test_cli_headless_mode():
    runner = CliRunner()
    # Mock create_provider and _run_headless
    with patch("henchman.cli.app._get_provider"), \
         patch("henchman.cli.app._run_headless", new_callable=AsyncMock) as mock_run:
        
        result = runner.invoke(main, ["--prompt", "hello"])
        assert result.exit_code == 0
        mock_run.assert_called_once()

def test_cli_interactive_mode():
    runner = CliRunner()
    with patch("henchman.cli.app._get_provider"), \
         patch("henchman.cli.app._run_interactive", new_callable=AsyncMock) as mock_run:
        
        result = runner.invoke(main, [])
        assert result.exit_code == 0
        mock_run.assert_called_once()

