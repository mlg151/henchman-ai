"""Default agent team presets."""

from henchman.agents.config import AgentConfig


def get_default_team() -> dict[str, AgentConfig]:
    """Get the default 4-agent team configuration.

    The Leader (Tech Lead) handles orchestration, delegation, and quality
    gating.  The Planner designs architectures and breaks down tasks.
    The Explorer researches and documents findings.  The Engineer
    implements code and runs tests.

    Returns:
        Dictionary mapping role ID to AgentConfig.
    """
    return {
        "planner": AgentConfig(
            name="Planner",
            role="planner",
            description="Architecture, task decomposition, and design docs in .agent_tasks/",
            tools=[
                "read_file",
                "write_file",
                "edit_file",
                "ls",
                "glob",
                "grep",
                "web_fetch",
                "web_search",
                "rag_search",
                "kg_query",
                "kg_update",
            ],
        ),
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
                "kg_query",
                "kg_update",
            ],
        ),
        "engineer": AgentConfig(
            name="Engineer",
            role="engineer",
            description="Code implementation, testing, and debugging",
            tools=[
                "read_file",
                "write_file",
                "edit_file",
                "ls",
                "glob",
                "grep",
                "shell",
            ],
        ),
    }
