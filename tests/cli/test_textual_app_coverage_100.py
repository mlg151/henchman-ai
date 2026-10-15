"""Tests to achieve 100% coverage for cli/textual_app.py.

Targets missing lines:
- 312-313: except Exception in _check_utf8_encoding
- 330-351: run_textual_app function (app.run and error paths)
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest


class TestCheckUtf8EncodingExceptionPath:
    """Tests for _check_utf8_encoding exception handling."""

    def test_check_utf8_exception_is_silently_caught(self) -> None:
        """Lines 312-313: non-AttributeError from encoding access is silently caught."""
        from henchman.cli.textual_app import _check_utf8_encoding

        class BadStdin:
            """stdin with a broken encoding property (raises TypeError)."""

            @property
            def encoding(self) -> str:
                """Raise TypeError to trigger the except clause."""
                raise TypeError("simulated codec error")

        with patch("henchman.cli.textual_app.sys") as mock_sys:
            mock_sys.platform = "linux"
            mock_sys.stdin = BadStdin()

            # Should not raise - the except Exception catches it
            _check_utf8_encoding()


class TestRunTextualApp:
    """Tests for run_textual_app function."""

    def test_run_textual_app_success(self) -> None:
        """Lines 330-344: run_textual_app creates app and calls app.run()."""
        from henchman.cli.textual_app import TextualConfig, run_textual_app

        mock_app = MagicMock()
        mock_provider = MagicMock()
        config = TextualConfig()
        settings = MagicMock()

        with (
            patch("henchman.cli.textual_app._check_utf8_encoding"),
            patch("henchman.cli.textual_app.HenchmanTextualApp", return_value=mock_app),
        ):
            run_textual_app(
                provider=mock_provider,
                config=config,
                settings=settings,
                environment_context="",
            )

        mock_app.run.assert_called_once()

    def test_run_textual_app_unicode_decode_error_prints_and_reraises(self) -> None:
        """Lines 345-347: UnicodeDecodeError is printed to stderr and re-raised."""
        from henchman.cli.textual_app import TextualConfig, run_textual_app

        mock_app = MagicMock()
        mock_app.run.side_effect = UnicodeDecodeError("utf-8", b"\xff", 0, 1, "invalid")
        mock_provider = MagicMock()

        with (
            patch("henchman.cli.textual_app._check_utf8_encoding"),
            patch("henchman.cli.textual_app.HenchmanTextualApp", return_value=mock_app),
            patch("builtins.print") as mock_print,
            pytest.raises(UnicodeDecodeError),
        ):
            run_textual_app(
                provider=mock_provider,
                config=TextualConfig(),
                settings=MagicMock(),
                environment_context="",
            )

        # Error message should have been printed
        mock_print.assert_called()

    def test_run_textual_app_exception_with_unicode_in_message_prints_and_reraises(self) -> None:
        """Lines 348-351: Exception with 'UnicodeDecodeError' in message prints and re-raises."""
        from henchman.cli.textual_app import TextualConfig, run_textual_app

        mock_app = MagicMock()
        mock_app.run.side_effect = RuntimeError("Caused by UnicodeDecodeError in driver")
        mock_provider = MagicMock()

        with (
            patch("henchman.cli.textual_app._check_utf8_encoding"),
            patch("henchman.cli.textual_app.HenchmanTextualApp", return_value=mock_app),
            patch("builtins.print") as mock_print,
            pytest.raises(RuntimeError),
        ):
            run_textual_app(
                provider=mock_provider,
                config=TextualConfig(),
                settings=MagicMock(),
                environment_context="",
            )

        mock_print.assert_called()

    def test_run_textual_app_other_exception_reraises_without_print(self) -> None:
        """Lines 348-351: Non-unicode Exception re-raises without printing unicode message."""
        from henchman.cli.textual_app import TextualConfig, run_textual_app

        mock_app = MagicMock()
        mock_app.run.side_effect = RuntimeError("Generic error, nothing to do with encoding")
        mock_provider = MagicMock()

        printed_args = []

        def capture_print(*args, **_kwargs):
            printed_args.extend(args)

        with (
            patch("henchman.cli.textual_app._check_utf8_encoding"),
            patch("henchman.cli.textual_app.HenchmanTextualApp", return_value=mock_app),
            patch("builtins.print", side_effect=capture_print),
            pytest.raises(RuntimeError),
        ):
            run_textual_app(
                provider=mock_provider,
                config=TextualConfig(),
                settings=MagicMock(),
                environment_context="",
            )

        # Unicode error message should NOT have been printed for non-unicode errors
        unicode_prints = [a for a in printed_args if "UnicodeDecodeError" in str(a)]
        assert not unicode_prints

    def test_run_textual_app_with_linux_driver(self) -> None:
        """Line 334-335: On Linux with RobustLinuxDriver, uses it as driver_class."""
        from henchman.cli.textual_app import TextualConfig, run_textual_app

        mock_app = MagicMock()
        mock_robust_driver = MagicMock()
        mock_provider = MagicMock()

        with (
            patch("henchman.cli.textual_app._check_utf8_encoding"),
            patch("henchman.cli.textual_app.sys") as mock_sys,
            patch("henchman.cli.textual_app.HenchmanTextualApp", return_value=mock_app) as mock_cls,
            patch("henchman.cli.textual_driver.RobustLinuxDriver", mock_robust_driver),
        ):
            mock_sys.platform = "linux"

            run_textual_app(
                provider=mock_provider,
                config=TextualConfig(),
                settings=MagicMock(),
                environment_context="",
            )

        mock_cls.assert_called_once()

    def test_run_textual_app_on_non_linux_uses_no_driver(self) -> None:
        """Branch 334->336: non-Linux platform sets driver_class to None."""
        from henchman.cli.textual_app import TextualConfig, run_textual_app

        mock_app = MagicMock()
        mock_provider = MagicMock()

        with (
            patch("henchman.cli.textual_app._check_utf8_encoding"),
            patch("henchman.cli.textual_app.sys") as mock_sys,
            patch("henchman.cli.textual_app.HenchmanTextualApp", return_value=mock_app) as mock_cls,
        ):
            mock_sys.platform = "darwin"  # Not Linux → driver_class = None

            run_textual_app(
                provider=mock_provider,
                config=TextualConfig(),
                settings=MagicMock(),
                environment_context="",
            )

        # driver_class should be None (False branch of 334)
        call_kwargs = mock_cls.call_args[1]
        assert call_kwargs.get("driver_class") is None
