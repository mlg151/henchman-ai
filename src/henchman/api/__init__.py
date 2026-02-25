"""Henchman-AI API module.

This module provides REST API access to Henchman-AI functionality.
"""

from henchman.api.server import app, run_server

__all__ = ["app", "run_server"]
