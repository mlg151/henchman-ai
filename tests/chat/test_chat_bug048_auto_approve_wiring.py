"""Test for BUG-048: auto_approve flag never connected to confirmation handler.

The ChatManager calls `tool_manager.set_auto_approve(auto_approve=True)` but
never calls `tool_manager.set_confirmation_handler()`, so the registry never
has a confirmation handler registered. This means `auto_approve` has no effect.

The fix: call `set_confirmation_handler()` to wire up the ToolManager's
`handle_confirmation` method as the registry's confirmation handler.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest


@pytest.mark.anyio
async def test_auto_approve_wired_to_registry() -> None:
    """set_auto_approve must be followed by set_confirmation_handler()."""
    from henchman.chat.manager import ChatManager

    settings = MagicMock()
    settings.providers.default = "deepseek"
    settings.providers.deepseek = {"model": "deepseek-chat"}
    settings.chat.discord.system_prompt = None

    manager = ChatManager(settings)

    # We'll inspect what happens inside _get_or_create_agent
    # by patching ToolManager at the import source
    with patch("henchman.cli.tool_manager.ToolManager") as mock_tool_manager_cls:
        mock_tool_manager = MagicMock()
        mock_tool_manager.registry = MagicMock()
        mock_tool_manager_cls.return_value = mock_tool_manager

        # Mock the registry and provider
        with patch("henchman.chat.manager.get_default_registry") as mock_registry:
            mock_provider = MagicMock()
            mock_registry.return_value.create.return_value = mock_provider

            with patch("henchman.chat.manager.get_api_key_for_provider", return_value=None):
                await manager._get_or_create_agent("test_user_123")

                # Verify set_auto_approve was called with True
                mock_tool_manager.set_auto_approve.assert_called_once_with(
                    auto_approve=True
                )

                # Verify set_confirmation_handler was called after set_auto_approve
                # to wire up the handler in the registry
                mock_tool_manager.set_confirmation_handler.assert_called_once()


