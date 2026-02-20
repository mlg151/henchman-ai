"""Tests for ThinkingMessage and ToolMessage boxes in ChatPane."""

import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from textual.app import App
from textual.widgets import Static

from henchman.cli.textual_app import (
    ChatPane,
    ThinkingMessage,
    HenchmanTextualApp,
    AgentThoughtMessage,
    ToolCallRequestMessage,
    ToolCallResultMessage,
)