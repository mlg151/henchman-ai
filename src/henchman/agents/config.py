"""Agent configuration module.

This module provides the AgentConfig class for configuring AI agents.
It re-exports the AgentConfig from the main configuration schema for
convenient access within the agents package.
"""

from henchman.config.schema import AgentConfig

__all__ = ["AgentConfig"]
