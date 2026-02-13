"""Behavioral evals for Skills and Memory system awareness.

These tests verify that the agent correctly recognizes when to use
learned skills and when to reference/store memories. Tests run against REAL LLM providers.
"""

from evals.helpers import eval_test


@eval_test("USUALLY_PASSES")
async def test_recognizes_skill_pattern(rig) -> None:
    """Agent should recognize when a task matches a learned skill pattern."""
    # Setup - create a skill file that the agent should recognize
    rig.create_file(
        ".henchman/skills/add-api-endpoint.yaml",
        """name: add-api-endpoint
description: Add a new REST API endpoint to a FastAPI application
steps:
  - Create route handler in routes/
  - Add Pydantic model for request/response
  - Register route in main.py
  - Add tests
parameters:
  - resource: The name of the resource (e.g., users, orders)
""",
    )
    rig.create_file(
        "main.py",
        """from fastapi import FastAPI

app = FastAPI()

@app.get("/health")
def health():
    return {"status": "ok"}
""",
    )

    # Run - ask to add an endpoint (matches the skill pattern)
    result = await rig.run(
        "Add a new API endpoint for managing 'products'. Check if there's a skill for this first."
    )

    # Assert: Agent should acknowledge the skill exists
    response_lower = result.final_response.lower()
    assert any(
        phrase in response_lower for phrase in ["skill", "add-api-endpoint", "pattern", "learned"]
    ), f"Agent should recognize the skill pattern. Got: {result.final_response[:500]}"


@eval_test("USUALLY_PASSES")
async def test_stores_important_fact_to_memory(rig) -> None:
    """Agent should recognize when to store important project facts."""
    # Setup - create a project with specific conventions
    rig.create_file(
        "pyproject.toml",
        """[project]
name = "myproject"

[tool.pytest.ini_options]
testpaths = ["tests"]
python_files = ["test_*.py"]
""",
    )
    rig.create_file(
        "tests/test_example.py",
        "def test_placeholder():\n    pass\n",
    )

    # Run - explicitly ask to remember something
    result = await rig.run(
        "Remember this: tests in this project must always use pytest fixtures, "
        "never setUp/tearDown methods. This is a team convention."
    )

    # Assert: Agent should acknowledge storing the memory
    response_lower = result.final_response.lower()
    assert any(
        phrase in response_lower
        for phrase in ["remember", "memory", "stored", "noted", "will keep"]
    ), f"Agent should acknowledge storing the memory. Got: {result.final_response[:500]}"


@eval_test("USUALLY_PASSES")
async def test_lists_skills_when_asked(rig) -> None:
    """Agent should list available skills when asked."""
    # Setup - create multiple skill files
    rig.create_file(
        ".henchman/skills/add-api-endpoint.yaml",
        "name: add-api-endpoint\ndescription: Add REST endpoint\n",
    )
    rig.create_file(
        ".henchman/skills/create-pytest-fixture.yaml",
        "name: create-pytest-fixture\ndescription: Create reusable pytest fixture\n",
    )

    # Run - ask about available skills (explicitly ask to look at files)
    result = await rig.run("Look in the .henchman/skills/ directory and list all available skills.")

    # Assert: Agent should read and list the skills
    assert (
        rig.tool_was_called("read_file") or rig.tool_was_called("ls") or rig.tool_was_called("glob")
    ), "Agent should explore the skills directory"
    # Response should mention at least one skill
    response_lower = result.final_response.lower()
    assert any(
        phrase in response_lower
        for phrase in ["add-api-endpoint", "create-pytest-fixture", "skill"]
    ), f"Agent should list available skills. Got: {result.final_response[:500]}"


@eval_test("USUALLY_PASSES")
async def test_uses_memory_context_appropriately(rig) -> None:
    """Agent should reference relevant memories when making decisions."""
    # Setup - create a HENCHMAN.md with project context (simulates memory)
    rig.create_file(
        "HENCHMAN.md",
        """# Project Context

## Conventions
- All functions must have type hints
- Use Google-style docstrings
- Never use print() for debugging - use logging module
- Tests go in tests/ directory, not alongside source
""",
    )
    rig.create_file(
        "src/utils.py",
        "def process(data):\n    print('Processing...')  # DEBUG\n    return data\n",
    )

    # Run - ask to review the code
    result = await rig.run(
        "Review src/utils.py. Does it follow our project conventions from HENCHMAN.md?"
    )

    # Assert: Agent should identify violations based on context
    response_lower = result.final_response.lower()
    assert any(
        phrase in response_lower
        for phrase in ["type hint", "print", "logging", "docstring", "convention", "violation"]
    ), f"Agent should identify convention violations. Got: {result.final_response[:500]}"


@eval_test("ALWAYS_PASSES")
async def test_reads_skill_file_when_asked(rig) -> None:
    """Agent should read skill files when explicitly asked about a specific skill."""
    # Setup - create a skill file with detailed content
    rig.create_file(
        ".henchman/skills/deploy-docker.yaml",
        """name: deploy-docker
description: Deploy application using Docker
steps:
  - Build Docker image with Dockerfile
  - Tag image with version
  - Push to registry
  - Update docker-compose.yml
parameters:
  - image_name: Name of the Docker image
  - version: Version tag (e.g., v1.0.0)
""",
    )

    # Run - explicitly ask to read and explain the skill
    result = await rig.run(
        "Read the skill file at .henchman/skills/deploy-docker.yaml and explain what it does."
    )

    # Assert: Agent should read the file
    assert rig.tool_was_called("read_file"), "Agent should read the skill file"

    # Response should contain skill details
    response_lower = result.final_response.lower()
    assert any(phrase in response_lower for phrase in ["docker", "deploy", "image", "build"]), (
        f"Agent should explain the skill content. Got: {result.final_response[:500]}"
    )


@eval_test("USUALLY_PASSES")
async def test_suggests_saving_skill_after_multi_step_task(rig) -> None:
    """Agent should suggest saving a pattern as a skill after complex tasks."""
    # Setup - a multi-file project
    rig.create_file(
        "src/__init__.py",
        "",
    )
    rig.create_file(
        "src/main.py",
        "def main():\n    pass\n",
    )
    rig.create_file(
        "tests/__init__.py",
        "",
    )

    # Run - ask for a multi-step task that could become a skill
    result = await rig.run(
        "Create a new module called 'validators' with a function 'validate_email' "
        "that validates email addresses, and add a test for it. "
        "After you're done, consider if this pattern should be saved as a skill."
    )

    # Assert: Agent should complete the task (create files)
    assert rig.tool_was_called("write_file"), "Agent should create the new files"
    _ = result  # Used for consistency, response not checked in this test

    # And ideally suggest saving as skill (but this is the aspirational part)
    # For now, just verify the task was completed
    calls = rig.get_tool_calls()
    write_calls = [c for c in calls if c["tool"] == "write_file"]
    assert len(write_calls) >= 1, "Agent should create at least the validator module"
