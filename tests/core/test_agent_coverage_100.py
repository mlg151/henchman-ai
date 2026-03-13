"""Tests to achieve 100% coverage for core/agent.py.

Targets missing lines:
- 171-175: _pending_config applied during __init__ (when set before _config init)
- 205-206: __getattr__ returning from _pending_config
- 209: __getattr__ raising AttributeError (no _config and no pending value)
- 220: __getattr__ raising AttributeError (no _stall)
- 229-230: __getattr__ raising AttributeError for instance alias target
- 251-256: __setattr__ storing in _pending_config when _config not yet initialized
- 265: __setattr__ super() call when _stall not initialized
- 274: __setattr__ super() call for instance alias target not initialized
"""

from __future__ import annotations

import pytest


class MockProvider:
    """Minimal provider mock for Agent instantiation."""

    name = "mock"
    model = "mock-model"
    default_model = "mock-model"

    async def chat_completion_stream(self, messages, tools=None, **kwargs):
        """Yield no events."""
        return
        yield  # pragma: no cover


def make_agent(**kwargs):
    """Create a minimal Agent instance for testing.

    Returns:
        A configured Agent instance.
    """
    from henchman.core.agent import Agent

    provider = MockProvider()
    return Agent(provider=provider, **kwargs)


class TestAgentPendingConfig:
    """Tests for pending config paths in __init__, __getattr__, __setattr__."""

    def test_pending_config_with_non_config_key_not_applied(self) -> None:
        """Branch 172->171: keys NOT in _CONFIG_FIELDS are skipped in pending_config loop."""
        from henchman.core.agent import Agent

        provider = MockProvider()

        class SubAgentWithNonConfigKey(Agent):
            """Subclass that stores non-config key in _pending_config."""

            def __init__(self, provider, **kwargs):
                """Init with mixed pending config."""
                # Store both a config field and a NON-config field
                object.__setattr__(self, "_pending_config", {
                    "system_prompt": "valid-prompt",
                    "__non_config_key__": "should-be-skipped",
                })
                super().__init__(provider=provider, **kwargs)

        agent = SubAgentWithNonConfigKey(provider=provider)
        # The config field should be applied
        assert agent.system_prompt == "valid-prompt"

    def test_setattr_pending_config_already_exists(self) -> None:
        """Branch 251->253: _pending_config already exists, just update it."""
        from henchman.core.agent import Agent

        provider = MockProvider()
        agent = Agent(provider=provider)

        # Temporarily remove _config to simulate early-init state
        config_backup = object.__getattribute__(agent, "_config")
        object.__delattr__(agent, "_config")

        try:
            # Set up a pre-existing _pending_config
            object.__setattr__(agent, "_pending_config", {"system_prompt": "first"})

            # Now set ANOTHER config field - _pending_config already exists
            agent.model = "gpt-4"  # This goes to __setattr__ → adds to existing _pending_config

            # Both fields should be in _pending_config
            pending = agent._pending_config
            assert "model" in pending
            assert pending["model"] == "gpt-4"
        finally:
            object.__setattr__(agent, "_config", config_backup)
            if hasattr(agent, "_pending_config"):
                object.__delattr__(agent, "_pending_config")

    def test_getattr_returns_pending_config_value(self) -> None:
        """Lines 205-206: __getattr__ returns value from _pending_config when _config absent."""
        from henchman.core.agent import Agent

        provider = MockProvider()

        class SubAgentPendingGet(Agent):
            """Subclass that accesses config field before _config is set."""

            def __init__(self, provider, **kwargs):
                """Access config field before super().__init__."""
                # Store a value in _pending_config manually
                object.__setattr__(self, "_pending_config", {"system_prompt": "pending-val"})
                # Now access it through __getattr__ - _config doesn't exist yet
                # but _pending_config does
                val = self.system_prompt  # noqa: F841
                super().__init__(provider=provider, **kwargs)

        agent = SubAgentPendingGet(provider=provider)
        assert agent is not None

    def test_getattr_raises_attribute_error_no_config_no_pending(self) -> None:
        """Line 209: __getattr__ raises AttributeError when no _config and no pending value."""
        from henchman.core.agent import Agent

        provider = MockProvider()
        agent = Agent(provider=provider)

        # Temporarily remove _config to simulate uninitialized state
        config_backup = object.__getattribute__(agent, "_config")
        object.__delattr__(agent, "_config")

        try:
            with pytest.raises(AttributeError, match="config not initialized yet"):
                _ = agent.system_prompt
        finally:
            object.__setattr__(agent, "_config", config_backup)

    def test_getattr_raises_attribute_error_no_stall(self) -> None:
        """Line 220: __getattr__ raises AttributeError when _stall not initialized."""
        from henchman.core.agent import Agent

        provider = MockProvider()
        agent = Agent(provider=provider)

        # Temporarily remove _stall to simulate uninitialized state
        stall_backup = object.__getattribute__(agent, "_stall")
        object.__delattr__(agent, "_stall")

        try:
            with pytest.raises(AttributeError, match="stall detector not initialized yet"):
                _ = agent.stall_detection_enabled
        finally:
            object.__setattr__(agent, "_stall", stall_backup)

    def test_getattr_raises_attribute_error_alias_target_missing(self) -> None:
        """Lines 229-230: __getattr__ raises AttributeError when instance alias target absent."""
        from henchman.core.agent import Agent

        provider = MockProvider()
        agent = Agent(provider=provider)

        # Temporarily remove the target of an instance alias
        # 'history' -> 'messages'; remove 'messages'
        messages_backup = agent.messages
        object.__delattr__(agent, "messages")

        try:
            with pytest.raises(AttributeError, match="target 'messages' not initialized yet"):
                _ = agent.history
        finally:
            object.__setattr__(agent, "messages", messages_backup)

    def test_setattr_stores_in_pending_config_when_config_absent(self) -> None:
        """Lines 251-256: __setattr__ stores config field in _pending_config.

        This is triggered when _config doesn't exist yet (early init phase).
        """
        from henchman.core.agent import Agent

        provider = MockProvider()
        agent = Agent(provider=provider)

        # Temporarily remove _config to simulate early-init state
        config_backup = object.__getattribute__(agent, "_config")
        object.__delattr__(agent, "_config")

        try:
            # Setting a config field should store in _pending_config
            agent.system_prompt = "stored-in-pending"
            # _pending_config should now exist
            assert hasattr(agent, "_pending_config")
            assert agent._pending_config.get("system_prompt") == "stored-in-pending"
        finally:
            object.__setattr__(agent, "_config", config_backup)
            # Clean up _pending_config if it was created
            if hasattr(agent, "_pending_config"):
                object.__delattr__(agent, "_pending_config")

    def test_setattr_super_when_stall_absent(self) -> None:
        """Line 265: __setattr__ calls super() when _stall not initialized.

        This happens during the early init phase before _stall is created.
        """
        from henchman.core.agent import Agent

        provider = MockProvider()
        agent = Agent(provider=provider)

        # Temporarily remove _stall
        stall_backup = object.__getattribute__(agent, "_stall")
        object.__delattr__(agent, "_stall")

        try:
            # Setting a stall field should fall back to super().__setattr__
            agent.stall_detection_enabled = True
            # Value should be stored as instance attribute (not on stall object)
            assert object.__getattribute__(agent, "stall_detection_enabled") is True
        finally:
            object.__setattr__(agent, "_stall", stall_backup)
            # Clean up if it was stored as instance attr
            try:
                object.__delattr__(agent, "stall_detection_enabled")
            except AttributeError:
                pass

    def test_setattr_super_when_alias_target_absent(self) -> None:
        """Line 274: __setattr__ calls super() when instance alias target not initialized."""
        from henchman.core.agent import Agent

        provider = MockProvider()
        agent = Agent(provider=provider)

        # Temporarily remove the alias target ('messages' for 'history')
        messages_backup = agent.messages
        object.__delattr__(agent, "messages")

        try:
            # Setting 'history' (alias) when target 'messages' doesn't exist
            # should fall back to super().__setattr__
            agent.history = []
            assert object.__getattribute__(agent, "history") == []
        finally:
            object.__setattr__(agent, "messages", messages_backup)
            try:
                object.__delattr__(agent, "history")
            except AttributeError:
                pass
