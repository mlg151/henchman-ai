"""Default agent team presets."""

from dataclasses import dataclass

from henchman.agents.config import AgentConfig

# Common tool sets to eliminate duplication
_BASIC_FILE_TOOLS = ["read_file", "ls", "glob", "grep", "tool_search"]
_CODE_DISCOVERY_TOOLS = ["file_overview", "symbol_trace", "pattern_search"]
_FILE_EDIT_TOOLS = ["write_file", "edit_file"]
_GIT_TOOLS = ["git_ops"]
_WEB_TOOLS = ["web_fetch", "web_search"]
_KNOWLEDGE_TOOLS = ["rag_search", "kg_query", "kg_update"]
_SHELL_TOOLS = ["shell"]
_PYTHON_DEV_TOOLS = [
    "python_exec",
    "pytest_run",
    "lint_check",
    "diff_view",
    "pip_inspect",
    "python_ast",
    "code_format",
    "traceback_parse",
    "import_graph",
    "coverage_map",
    "dead_code",
    "env_inspect",
    "test_gen",
    "patch_apply",
]


@dataclass
class ToolCategoryConfig:
    """Configuration for tool categories to include in an agent.

    This dataclass groups related boolean parameters that control which
    tool categories are enabled for an agent configuration.
    """

    basic_file_tools: bool = True
    file_edit_tools: bool = False
    git_tools: bool = True
    web_tools: bool = False
    knowledge_tools: bool = False
    shell_tools: bool = False
    python_dev_tools: bool = False
    code_discovery_tools: bool = False


def _create_agent_config(
    name: str,
    role: str,
    description: str,
    *,
    tool_categories: ToolCategoryConfig | None = None,
    special_tools: list[str] | None = None,
) -> AgentConfig:
    """Create an agent configuration with specified tool categories.

    Args:
        name: Agent display name
        role: Agent role identifier
        description: Agent description
        tool_categories: Configuration for which tool categories to include.
            If None, uses default ToolCategoryConfig().
        special_tools: Additional special tools like delegate_task, ask_user

    Returns:
        AgentConfig with appropriate tools
    """
    if tool_categories is None:
        tool_categories = ToolCategoryConfig()

    tools: list[str] = ["goal_status"]

    if tool_categories.basic_file_tools:
        tools.extend(_BASIC_FILE_TOOLS)
    if tool_categories.code_discovery_tools:
        tools.extend(_CODE_DISCOVERY_TOOLS)
    if tool_categories.file_edit_tools:
        tools.extend(_FILE_EDIT_TOOLS)
    if tool_categories.git_tools:
        tools.extend(_GIT_TOOLS)
    if tool_categories.web_tools:
        tools.extend(_WEB_TOOLS)
    if tool_categories.knowledge_tools:
        tools.extend(_KNOWLEDGE_TOOLS)
    if tool_categories.shell_tools:
        tools.extend(_SHELL_TOOLS)
    if tool_categories.python_dev_tools:
        tools.extend(_PYTHON_DEV_TOOLS)
    if tool_categories.shell_tools or tool_categories.python_dev_tools:
        tools.extend(["task_get", "task_list", "task_output", "task_stop"])
    if special_tools:
        tools.extend(special_tools)

    return AgentConfig(
        name=name,
        role=role,
        description=description,
        tools=tools,
    )


def _create_tech_lead_config() -> AgentConfig:
    """Create the primary coding agent with full live workspace tooling."""
    return AgentConfig(
        name="Primary",
        role="tech_lead",
        description="Primary coding agent with direct tools and dynamic background subagents",
        tools=["*"],
    )


def _create_planner_config() -> AgentConfig:
    """Create configuration for the Planner agent.

    The Planner designs architectures and breaks down tasks.
    """
    return _create_agent_config(
        name="Planner",
        role="planner",
        description="Architecture, task decomposition, and design docs.",
        tool_categories=ToolCategoryConfig(
            basic_file_tools=True,
            code_discovery_tools=True,
            file_edit_tools=True,  # Can write design docs
            git_tools=True,
            web_tools=True,
            knowledge_tools=True,
            shell_tools=False,
            python_dev_tools=False,
        ),
    )


def _create_explorer_config() -> AgentConfig:
    """Create configuration for the Explorer agent.

    The Explorer researches, analyzes, and documents findings.
    """
    return _create_agent_config(
        name="Explorer",
        role="explorer",
        description="Research, analysis, and documentation.",
        tool_categories=ToolCategoryConfig(
            basic_file_tools=True,
            code_discovery_tools=True,
            file_edit_tools=True,  # Can write documentation
            git_tools=True,
            web_tools=True,
            knowledge_tools=True,
            shell_tools=True,  # For research tasks
            python_dev_tools=False,
        ),
    )


def _create_engineer_config() -> AgentConfig:
    """Create configuration for the Engineer agent.

    The Engineer implements code, runs tests, and debugs.
    """
    return _create_agent_config(
        name="Engineer",
        role="engineer",
        description="Code implementation, testing, and debugging",
        tool_categories=ToolCategoryConfig(
            basic_file_tools=True,
            code_discovery_tools=True,
            file_edit_tools=True,  # Can write code
            git_tools=True,
            web_tools=False,
            knowledge_tools=False,
            shell_tools=True,  # For running tests and commands
            python_dev_tools=True,  # Full Python development toolset
        ),
    )


def _create_data_engineer_config() -> AgentConfig:
    """Create configuration for the Data Engineer agent.

    The Data Engineer builds data pipelines, Spark/Pandas transformations,
    AWS infrastructure, and Airflow orchestration.
    """
    return _create_agent_config(
        name="Data Engineer",
        role="data_engineer",
        description="Data pipeline development, PySpark/Pandas transformations, AWS infrastructure, and Airflow orchestration",
        tool_categories=ToolCategoryConfig(
            basic_file_tools=True,
            code_discovery_tools=True,
            file_edit_tools=True,  # Can write code and configs
            git_tools=True,
            web_tools=True,  # For AWS/cloud research
            knowledge_tools=False,
            shell_tools=True,  # For data pipeline operations
            python_dev_tools=True,  # Full Python development toolset
        ),
    )


def get_default_team() -> dict[str, AgentConfig]:
    """Get the default 5-agent team configuration.

    The Leader (Tech Lead) handles orchestration, delegation, and quality
    gating.  The Planner designs architectures and breaks down tasks.
    The Explorer researches and documents findings.  The Engineer
    implements code and runs tests.  The Data Engineer builds data
    pipelines, Spark/Pandas transformations, and Airflow DAGs.

    Returns:
        Dictionary mapping role ID to AgentConfig.
    """
    return {
        "tech_lead": _create_tech_lead_config(),
        "planner": _create_planner_config(),
        "explorer": _create_explorer_config(),
        "engineer": _create_engineer_config(),
        "data_engineer": _create_data_engineer_config(),
    }
