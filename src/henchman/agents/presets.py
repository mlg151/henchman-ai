"""Default agent team presets."""

from henchman.agents.config import AgentConfig

# Common tool sets to eliminate duplication
_BASIC_FILE_TOOLS = ["read_file", "ls", "glob", "grep"]
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


def _create_agent_config(
    name: str,
    role: str,
    description: str,
    *,
    basic_file_tools: bool = True,
    file_edit_tools: bool = False,
    git_tools: bool = True,
    web_tools: bool = False,
    knowledge_tools: bool = False,
    shell_tools: bool = False,
    python_dev_tools: bool = False,
    special_tools: list[str] | None = None,
) -> AgentConfig:
    """Create an agent configuration with specified tool categories.

    Args:
        name: Agent display name
        role: Agent role identifier
        description: Agent description
        basic_file_tools: Include read_file, ls, glob, grep
        file_edit_tools: Include write_file, edit_file
        git_tools: Include git_ops
        web_tools: Include web_fetch, web_search
        knowledge_tools: Include rag_search, kg_query, kg_update
        shell_tools: Include shell
        python_dev_tools: Include python development tools
        special_tools: Additional special tools like delegate_task, ask_user

    Returns:
        AgentConfig with appropriate tools
    """
    tools: list[str] = []

    if basic_file_tools:
        tools.extend(_BASIC_FILE_TOOLS)
    if file_edit_tools:
        tools.extend(_FILE_EDIT_TOOLS)
    if git_tools:
        tools.extend(_GIT_TOOLS)
    if web_tools:
        tools.extend(_WEB_TOOLS)
    if knowledge_tools:
        tools.extend(_KNOWLEDGE_TOOLS)
    if shell_tools:
        tools.extend(_SHELL_TOOLS)
    if python_dev_tools:
        tools.extend(_PYTHON_DEV_TOOLS)
    if special_tools:
        tools.extend(special_tools)

    return AgentConfig(
        name=name,
        role=role,
        description=description,
        tools=tools,
    )


def _create_tech_lead_config() -> AgentConfig:
    """Create configuration for the Tech Lead agent.

    The Tech Lead handles orchestration, delegation, and quality gating.
    Read-only, delegates all writes.
    """
    return _create_agent_config(
        name="Leader",
        role="tech_lead",
        description="Orchestrator, delegator, and quality gate — read-only, delegates all writes",
        basic_file_tools=True,
        file_edit_tools=False,  # Read-only, delegates writes
        git_tools=True,
        web_tools=True,
        knowledge_tools=True,
        shell_tools=True,
        python_dev_tools=False,
        special_tools=["delegate_task", "ask_user"],
    )


def _create_planner_config() -> AgentConfig:
    """Create configuration for the Planner agent.

    The Planner designs architectures and breaks down tasks.
    Creates design docs in .agent_tasks/.
    """
    return _create_agent_config(
        name="Planner",
        role="planner",
        description="Architecture, task decomposition, and design docs in .agent_tasks/",
        basic_file_tools=True,
        file_edit_tools=True,  # Can write design docs
        git_tools=True,
        web_tools=True,
        knowledge_tools=True,
        shell_tools=False,
        python_dev_tools=False,
    )


def _create_explorer_config() -> AgentConfig:
    """Create configuration for the Explorer agent.

    The Explorer researches, analyzes, and documents findings.
    Creates documentation in .agent_tasks/.
    """
    return _create_agent_config(
        name="Explorer",
        role="explorer",
        description="Research, analysis, and documentation in .agent_tasks/",
        basic_file_tools=True,
        file_edit_tools=True,  # Can write documentation
        git_tools=True,
        web_tools=True,
        knowledge_tools=True,
        shell_tools=True,  # For research tasks
        python_dev_tools=False,
    )


def _create_engineer_config() -> AgentConfig:
    """Create configuration for the Engineer agent.

    The Engineer implements code, runs tests, and debugs.
    """
    return _create_agent_config(
        name="Engineer",
        role="engineer",
        description="Code implementation, testing, and debugging",
        basic_file_tools=True,
        file_edit_tools=True,  # Can write code
        git_tools=True,
        web_tools=False,
        knowledge_tools=False,
        shell_tools=True,  # For running tests and commands
        python_dev_tools=True,  # Full Python development toolset
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
        basic_file_tools=True,
        file_edit_tools=True,  # Can write code and configs
        git_tools=True,
        web_tools=True,  # For AWS/cloud research
        knowledge_tools=False,
        shell_tools=True,  # For data pipeline operations
        python_dev_tools=True,  # Full Python development toolset
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
