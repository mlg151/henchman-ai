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


def _create_tech_lead_config() -> AgentConfig:
    """Create configuration for the Tech Lead agent.

    The Tech Lead handles orchestration, delegation, and quality gating.
    Read-only, delegates all writes.
    """
    return AgentConfig(
        name="Leader",
        role="tech_lead",
        description="Orchestrator, delegator, and quality gate — read-only, delegates all writes",
        tools=_BASIC_FILE_TOOLS
        + _SHELL_TOOLS
        + _GIT_TOOLS
        + _WEB_TOOLS
        + _KNOWLEDGE_TOOLS
        + ["delegate_task", "ask_user"],
    )


def _create_planner_config() -> AgentConfig:
    """Create configuration for the Planner agent.

    The Planner designs architectures and breaks down tasks.
    Creates design docs in .agent_tasks/.
    """
    return AgentConfig(
        name="Planner",
        role="planner",
        description="Architecture, task decomposition, and design docs in .agent_tasks/",
        tools=_BASIC_FILE_TOOLS
        + _FILE_EDIT_TOOLS
        + _GIT_TOOLS
        + _WEB_TOOLS
        + _KNOWLEDGE_TOOLS,
    )


def _create_explorer_config() -> AgentConfig:
    """Create configuration for the Explorer agent.

    The Explorer researches, analyzes, and documents findings.
    Creates documentation in .agent_tasks/.
    """
    return AgentConfig(
        name="Explorer",
        role="explorer",
        description="Research, analysis, and documentation in .agent_tasks/",
        tools=_BASIC_FILE_TOOLS
        + _FILE_EDIT_TOOLS
        + _SHELL_TOOLS
        + _GIT_TOOLS
        + _WEB_TOOLS
        + _KNOWLEDGE_TOOLS,
    )


def _create_engineer_config() -> AgentConfig:
    """Create configuration for the Engineer agent.

    The Engineer implements code, runs tests, and debugs.
    """
    return AgentConfig(
        name="Engineer",
        role="engineer",
        description="Code implementation, testing, and debugging",
        tools=_BASIC_FILE_TOOLS
        + _FILE_EDIT_TOOLS
        + _SHELL_TOOLS
        + _GIT_TOOLS
        + _PYTHON_DEV_TOOLS,
    )


def _create_data_engineer_config() -> AgentConfig:
    """Create configuration for the Data Engineer agent.

    The Data Engineer builds data pipelines, Spark/Pandas transformations,
    AWS infrastructure, and Airflow orchestration.
    """
    return AgentConfig(
        name="Data Engineer",
        role="data_engineer",
        description="Data pipeline development, PySpark/Pandas transformations, AWS infrastructure, and Airflow orchestration",
        tools=_BASIC_FILE_TOOLS
        + _FILE_EDIT_TOOLS
        + _SHELL_TOOLS
        + _GIT_TOOLS
        + _WEB_TOOLS
        + _PYTHON_DEV_TOOLS,
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
