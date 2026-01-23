"""Tests for __main__ module entry point."""

import subprocess
import sys

from mlg import __main__  # Test that module can be imported
from mlg.cli.app import main


def test_main_module_imports() -> None:
    """Test that __main__ module imports correctly."""
    assert hasattr(__main__, "main")
    assert __main__.main is main


def test_python_m_mlg_version() -> None:
    """Test that python -m mlg --version works."""
    result = subprocess.run(
        [sys.executable, "-m", "mlg", "--version"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "0.1.0" in result.stdout


def test_python_m_mlg_help() -> None:
    """Test that python -m mlg --help works."""
    result = subprocess.run(
        [sys.executable, "-m", "mlg", "--help"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "--version" in result.stdout
    assert "--help" in result.stdout
