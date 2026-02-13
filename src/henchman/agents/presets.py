"""Default agent team presets."""

from henchman.agents.config import AgentConfig


def get_default_team() -> dict[str, AgentConfig]:
    """Get the default 2-agent team configuration.

    The Leader (Tech Lead) handles planning, coding, architecture,
    testing, and review directly.  The Explorer is a lightweight
    subagent for research and documentation that writes findings
    into the `.agent_tasks/` workspace.

    Returns:
        Dictionary mapping role ID to AgentConfig.
    """
    return {
        "explorer": AgentConfig(
            name="Explorer",
            role="explorer",
            description="Research, analysis, and documentation in .agent_tasks/",
            tools=[
                "read_file",
                "write_file",
                "edit_file",
                "ls",
                "glob",
                "grep",
                "shell",
                "web_fetch",
                "web_search",
                "rag_search",
            ],
        ),
    }
