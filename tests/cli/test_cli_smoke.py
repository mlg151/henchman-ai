"""
Smoke tests for the CLI entry point.

These tests verify that the CLI can actually start without crashing,
catching integration issues that unit tests with mocks might miss.
"""

import subprocess
import sys


class TestCLISmoke:
    """Smoke tests for CLI startup."""

    def test_cli_help_works(self):
        """Test that 'henchman --help' runs without errors."""
        result = subprocess.run(
            [sys.executable, "-m", "henchman", "--help"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        assert result.returncode == 0
        # Check for CLI options instead of specific branding text
        assert "--prompt" in result.stdout
        assert "--help" in result.stdout

    def test_cli_version_works(self):
        """Test that 'henchman --version' runs without errors."""
        result = subprocess.run(
            [sys.executable, "-m", "henchman", "--version"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        assert result.returncode == 0
        # Version should be in output
        assert "0." in result.stdout or "1." in result.stdout

    def test_cli_module_import(self):
        """Test that the CLI module can be imported without errors."""
        # This catches import-time errors
        from henchman.cli.app import _get_provider, _run_interactive, cli, main

        assert callable(cli)
        assert callable(main)
        assert callable(_get_provider)
        assert callable(_run_interactive)

    def test_repl_can_be_instantiated(self):
        """Test that Repl can be instantiated with all expected arguments."""
        from unittest.mock import Mock

        from henchman.cli.repl import Repl, ReplConfig
        from henchman.config.schema import Settings

        # This tests the actual Repl signature matches what app.py expects
        mock_provider = Mock()
        config = ReplConfig()
        settings = Settings()

        # This should not raise TypeError
        repl = Repl(
            provider=mock_provider,
            console=None,
            config=config,
            settings=settings,
        )

        assert repl.provider is mock_provider
        assert repl.settings is settings
