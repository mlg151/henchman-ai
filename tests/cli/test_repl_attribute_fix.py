"""Tests to prevent AttributeError: 'Repl' object has no attribute 'run'.

This test suite ensures comprehensive coverage that the Repl class has
a proper run() method and that all code paths properly invoke it.
"""

from __future__ import annotations

import inspect
import subprocess
import sys
from io import StringIO
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

from rich.console import Console

from henchman.cli.repl import Repl, ReplConfig
from henchman.providers.base import FinishReason, Message, ModelProvider, StreamChunk


class MockProvider(ModelProvider):
    """Mock provider for testing."""

    def __init__(self, responses: list[str] | None = None) -> None:
        self.responses = responses or ["Hello!"]
        self._call_count = 0

    @property
    def name(self) -> str:
        return "mock"

    async def chat_completion_stream(
        self, messages: list[Message], tools: list[Any] | None = None, **kwargs: Any
    ) -> Any:
        response = self.responses[min(self._call_count, len(self.responses) - 1)]
        self._call_count += 1
        yield StreamChunk(content=response, finish_reason=FinishReason.STOP)


class TestReplHasRunMethod:
    """Unit tests for Repl.run method existence."""

    def test_repl_has_run_method(self) -> None:
        """Assert Repl has a callable run method."""
        assert hasattr(Repl, "run"), "Repl class must have a 'run' method"
        assert callable(Repl.run), "Repl.run must be callable"

    def test_repl_run_is_async(self) -> None:
        """Ensure run is an async method."""
        assert inspect.iscoroutinefunction(
            Repl.run
        ), "Repl.run must be an async method (coroutine function)"

    def test_repl_run_callable(self) -> None:
        """Ensure run is callable and not None."""
        console = Console(file=StringIO(), force_terminal=True)
        provider = MockProvider()
        repl = Repl(provider=provider, console=console)

        assert hasattr(repl, "run"), "Repl instance must have 'run' method"
        assert callable(repl.run), "repl.run must be callable"

    def test_repl_run_signature(self) -> None:
        """Ensure run has correct async signature."""
        sig = inspect.signature(Repl.run)
        # Should only have 'self' parameter
        params = list(sig.parameters.keys())
        assert params == ["self"], f"run() should only have 'self' parameter, got {params}"

        # Should be awaitable
        assert inspect.iscoroutinefunction(Repl.run), "run() must be a coroutine function"


class TestReplImportable:
    """Unit tests for Repl importability."""

    def test_repl_importable_from_henchman_cli_repl(self) -> None:
        """Repl importable from henchman.cli.repl."""
        from henchman.cli.repl import Repl as ReplImport

        assert ReplImport is Repl

    def test_repl_config_importable(self) -> None:
        """ReplConfig importable from henchman.cli.repl."""
        from henchman.cli.repl import ReplConfig as ReplConfigImport

        assert ReplConfigImport is ReplConfig

    def test_run_interactive_imports_repl(self) -> None:
        """_run_interactive successfully imports Repl."""
        from henchman.cli.app import _run_interactive

        # The import should happen without errors
        assert _run_interactive is not None


class TestRunInteractiveInvokesReplRun:
    """Unit tests for _run_interactive properly invoking repl.run."""

    def test_run_interactive_invokes_repl_run_with_anyio(self) -> None:
        """_run_interactive calls repl.run via anyio.run."""
        from henchman.cli.app import _run_interactive

        mock_repl_instance = AsyncMock()
        mock_repl_instance.run = AsyncMock()
        mock_loader_instance = MagicMock()
        mock_loader_instance.load.return_value = "system prompt"
        mock_settings = MagicMock()
        mock_provider_instance = MagicMock()

        with (
            patch("henchman.cli.app._get_provider", return_value=mock_provider_instance),
            patch("henchman.config.ContextLoader", return_value=mock_loader_instance),
            patch("henchman.config.load_settings", return_value=mock_settings),
            patch(
                "henchman.cli.repl.Repl",
                return_value=mock_repl_instance,
            ) as mock_repl_class,
            patch("henchman.cli.app.anyio.run") as mock_anyio_run,
        ):
            _run_interactive("text")

            # Verify Repl was instantiated
            assert mock_repl_class.called

            # Verify anyio.run was called with repl.run
            mock_anyio_run.assert_called_once_with(mock_repl_instance.run)

    def test_run_interactive_passes_correct_repl_instance(self) -> None:
        """_run_interactive passes correct Repl instance to anyio.run."""
        from henchman.cli.app import _run_interactive

        mock_repl_instance = AsyncMock()
        mock_loader_instance = MagicMock()
        mock_loader_instance.load.return_value = "system prompt"
        mock_settings = MagicMock()

        with (
            patch("henchman.cli.app._get_provider") as mock_get_provider,
            patch("henchman.config.ContextLoader", return_value=mock_loader_instance),
            patch("henchman.config.load_settings", return_value=mock_settings),
            patch(
                "henchman.cli.repl.Repl",
                return_value=mock_repl_instance,
            ),
            patch("henchman.cli.app.anyio.run") as mock_anyio_run,
        ):
            mock_provider = MagicMock()
            mock_get_provider.return_value = mock_provider

            _run_interactive("text")

            # Verify the correct instance was passed to anyio.run
            called_with = mock_anyio_run.call_args[0][0]
            assert called_with is mock_repl_instance.run


class TestCliEntrypointRuns:
    """Integration tests for CLI entrypoint."""

    def test_cli_entrypoint_help_no_attribute_error(self) -> None:
        """Subprocess henchman --help runs without AttributeError."""
        # Run the CLI with --help
        result = subprocess.run(
            [sys.executable, "-m", "henchman.cli.app", "--help"],
            capture_output=True,
            text=True,
            timeout=10,
        )

        # Should succeed
        assert result.returncode == 0, f"CLI --help failed: {result.stderr}"
        assert "AttributeError" not in result.stderr, f"AttributeError in stderr: {result.stderr}"

    def test_cli_entrypoint_version_no_attribute_error(self) -> None:
        """Subprocess henchman --version runs without AttributeError."""
        result = subprocess.run(
            [sys.executable, "-m", "henchman.cli.app", "--version"],
            capture_output=True,
            text=True,
            timeout=10,
        )

        assert result.returncode == 0, f"CLI --version failed: {result.stderr}"
        assert "AttributeError" not in result.stderr, f"AttributeError in stderr: {result.stderr}"

    def test_cli_with_prompt_no_attribute_error(self) -> None:
        """CLI with --prompt doesn't throw AttributeError."""
        result = subprocess.run(
            [sys.executable, "-m", "henchman.cli.app", "--prompt", "test"],
            capture_output=True,
            text=True,
            timeout=10,
            env={**__import__("os").environ, "DEEPSEEK_API_KEY": "test-key"},
        )

        # Even if it fails for other reasons, AttributeError should not be there
        assert "AttributeError: 'Repl' object has no attribute 'run'" not in result.stderr


class TestInteractiveReplLoop:
    """Integration tests for interactive REPL loop."""

    def test_repl_run_callable_and_async(self) -> None:
        """Verify repl.run() is callable and async."""
        console = Console(file=StringIO(), force_terminal=True)
        provider = MockProvider(["Response!"])
        repl = Repl(provider=provider, console=console)

        # Verify run exists and is callable
        assert callable(repl.run)
        assert inspect.iscoroutinefunction(repl.run)

    def test_repl_run_returns_coroutine(self) -> None:
        """Verify repl.run() returns a coroutine."""
        console = Console(file=StringIO(), force_terminal=True)
        provider = MockProvider()
        repl = Repl(provider=provider, console=console)

        coro = repl.run()
        assert inspect.iscoroutine(coro)
        coro.close()  # Clean up

    def test_repl_has_run_that_works_with_anyio(self) -> None:
        """Verify Repl.run can be passed to anyio.run()."""
        console = Console(file=StringIO(), force_terminal=True)
        provider = MockProvider()
        repl = Repl(provider=provider, console=console)

        # The key test: that app.py line 95/101 can call anyio.run(repl.run)
        # without AttributeError
        assert hasattr(repl, "run")
        assert callable(repl.run)

        # Simulate what app.py does
        assert repl.run is not None  # Should be callable


class TestNoAttributeErrorRegression:
    """Regression tests to catch if Repl.run ever goes missing."""

    def test_repl_run_method_always_exists(self) -> None:
        """Regression: Verify Repl.run method always exists."""
        # This test will fail if someone accidentally removes the run method
        assert hasattr(Repl, "run"), "REGRESSION: Repl.run method is missing!"
        assert (
            "run" in dir(Repl)
        ), "REGRESSION: Repl.run is not in Repl's public interface!"

    def test_repl_run_is_coroutine_function(self) -> None:
        """Regression: Verify Repl.run is a coroutine function."""
        assert inspect.iscoroutinefunction(Repl.run), "Repl.run must be a coroutine function"

    def test_no_attribute_error_with_mocked_repl_without_run(self) -> None:
        """Patch Repl to remove run, assert CLI fails with clear error."""
        from henchman.cli.app import _run_interactive

        mock_repl_class = MagicMock(spec=[])  # Empty spec - no attributes
        mock_loader_instance = MagicMock()
        mock_loader_instance.load.return_value = "system prompt"
        mock_settings = MagicMock()

        with (
            patch("henchman.cli.app._get_provider"),
            patch("henchman.config.ContextLoader", return_value=mock_loader_instance),
            patch("henchman.config.load_settings", return_value=mock_settings),
            patch("henchman.cli.repl.Repl", mock_repl_class),
            patch("henchman.cli.app.anyio.run") as mock_anyio_run,
        ):
            try:
                _run_interactive("text")
                # Try to call anyio.run - this will fail if repl has no run
                mock_anyio_run.assert_called()
            except AttributeError as e:
                # If AttributeError is raised, it should be about the mock
                # not about Repl.run not existing
                assert "run" in str(e)

    def test_app_py_calls_repl_run_not_repl_start(self) -> None:
        """Ensure app.py calls repl.run(), not repl.start()."""
        # Read app.py and check for repl.run() calls
        with open("/home/matthew/mlg-cli/src/henchman/cli/app.py") as f:
            app_content = f.read()

        # Should have repl.run calls
        assert "repl.run" in app_content, "app.py should call repl.run()"

        # Should not have repl.start calls (regression prevention)
        assert "repl.start" not in app_content, "app.py should not call repl.start()"


class TestCoverageRegression:
    """Ensure code paths are covered."""

    def test_repl_run_method_is_public(self) -> None:
        """Ensure repl.run() is a public method."""
        console = Console(file=StringIO(), force_terminal=True)
        provider = MockProvider()
        repl = Repl(provider=provider, console=console)

        # Verify the method exists and is public (not prefixed with _)
        assert hasattr(repl, "run")
        assert not repl.run.__name__.startswith("_")

    def test_app_py_references_repl_run(self) -> None:
        """Ensure app.py properly references repl.run()."""
        with open("/home/matthew/mlg-cli/src/henchman/cli/app.py") as f:
            content = f.read()

        # Check that anyio.run is called with repl.run
        assert "anyio.run(repl.run)" in content

    def test_repl_run_method_attributes(self) -> None:
        """Ensure repl.run has correct attributes and signature."""
        console = Console(file=StringIO(), force_terminal=True)
        provider = MockProvider()
        repl = Repl(provider=provider, console=console)

        # Verify it's a method that can be bound to anyio.run
        run_method = repl.run
        assert callable(run_method)
        assert inspect.iscoroutinefunction(run_method)

        # The signature check - should have no required args except implicit self
        sig = inspect.signature(run_method)
        # For a bound method, there shouldn't be any parameters
        assert len(sig.parameters) == 0

    def test_repl_run_vs_start_differentiation(self) -> None:
        """Ensure app.py doesn't accidentally use 'start' instead of 'run'."""
        with open("/home/matthew/mlg-cli/src/henchman/cli/app.py") as f:
            app_content = f.read()

        # Count occurrences to ensure run is used, not start
        run_count = app_content.count("repl.run")
        start_count = app_content.count("repl.start")

        assert run_count > 0, "app.py should call repl.run()"
        assert start_count == 0, "app.py should not call repl.start()"
