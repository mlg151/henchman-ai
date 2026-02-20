"""Default agent team presets."""

from henchman.agents.config import AgentConfig


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
        "tech_lead": AgentConfig(
            name="Leader",
            role="tech_lead",
            description="Orchestrator, delegator, and quality gate — read-only, delegates all writes",
            tools=[
                "read_file",
                "ls",
                "glob",
                "grep",
                "shell",
                "web_fetch",
                "web_search",
                "rag_search",
                "kg_query",
                "kg_update",
                "delegate_task",
                "ask_user",
            ],
        ),
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
            ],
        ),
        "data_engineer": AgentConfig(
            name="Data Engineer",
            role="data_engineer",
            description="Data pipeline development, PySpark/Pandas transformations, AWS infrastructure, and Airflow orchestration",
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
            ],
        ),
    }
