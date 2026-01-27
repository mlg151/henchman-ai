"""Tests for __main__ module entry point."""

import subprocess
import sys

from henchman import __main__  # Test that module can be imported
from henchman.cli.app import main


def test_main_module_imports() -> None:
    """Test that __main__ module imports correctly."""
    assert hasattr(__main__, "main")
    assert __main__.main is main


    def test_python_m_henchman_version() -> None:
        """Test that python -m henchman --version works."""
        result = subprocess.run(
            [sys.executable, "-m", "henchman", "--version"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        assert "0.1.7" in result.stdout

def test_python_m_henchman_help() -> None:
    """Test that python -m henchman --help works."""
    result = subprocess.run(
        [sys.executable, "-m", "henchman", "--help"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "--version" in result.stdout
    assert "--help" in result.stdout
