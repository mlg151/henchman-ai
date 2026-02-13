"""Behavioral evals for tool selection.

These tests verify that the agent correctly chooses which tools to use
based on the user's request. Tests run against REAL LLM providers.
"""

from evals.helpers import eval_test


@eval_test("ALWAYS_PASSES")
async def test_uses_read_file_for_reading(rig) -> None:
    """Agent should use read_file tool when asked to read a file."""
    # Setup: Create a file to read
    rig.create_file("example.txt", "Hello World from the test file!")

    # Run the agent with a clear request
    await rig.run("Read the contents of example.txt and tell me what it says.")

    # Assert: Agent should have called read_file
    assert rig.tool_was_called("read_file"), "Agent should call read_file tool"


@eval_test("ALWAYS_PASSES")
async def test_uses_ls_for_listing_directory(rig) -> None:
    """Agent should use ls tool when asked to list files."""
    # Setup: Create some files
    rig.create_file("file1.txt", "content1")
    rig.create_file("file2.txt", "content2")
    rig.create_file("subdir/file3.txt", "content3")

    # Run
    await rig.run("List all files in the current directory.")

    # Assert
    assert rig.tool_was_called("ls"), "Agent should call ls tool"


@eval_test("ALWAYS_PASSES")
async def test_uses_write_file_for_creating(rig) -> None:
    """Agent should use write_file tool when asked to create a file."""
    # Run
    await rig.run("Create a new file called hello.txt with the content 'Hello World!'")

    # Assert
    assert rig.tool_was_called("write_file"), "Agent should call write_file tool"
    # Verify the file was actually created
    assert rig.file_exists("hello.txt"), "File should have been created"


@eval_test("ALWAYS_PASSES")
async def test_uses_grep_for_searching(rig) -> None:
    """Agent should use grep tool when asked to search for text."""
    # Setup
    rig.create_file("code.py", "def hello_world():\n    print('Hello World')\n")
    rig.create_file("other.py", "def goodbye():\n    print('Goodbye')\n")

    # Run
    await rig.run("Search for the text 'hello' in all Python files.")

    # Assert
    assert rig.tool_was_called("grep"), "Agent should call grep tool"


@eval_test("ALWAYS_PASSES")
async def test_uses_glob_for_finding_files(rig) -> None:
    """Agent should use glob tool when asked to find files by pattern."""
    # Setup
    rig.create_file("src/main.py", "# main")
    rig.create_file("src/utils.py", "# utils")
    rig.create_file("tests/test_main.py", "# tests")
    rig.create_file("README.md", "# Readme")

    # Run
    await rig.run("Find all Python files (*.py) in this project.")

    # Assert
    assert rig.tool_was_called("glob"), "Agent should call glob tool"


@eval_test("USUALLY_PASSES")
async def test_uses_shell_for_running_commands(rig) -> None:
    """Agent should use shell tool when asked to run a command."""
    # Run
    await rig.run("Run the command 'echo Hello from shell' and show me the output.")

    # Assert
    assert rig.tool_was_called("shell"), "Agent should call shell tool"


@eval_test("USUALLY_PASSES")
async def test_uses_edit_for_modifying_files(rig) -> None:
    """Agent should use edit_file tool when asked to modify existing content."""
    # Setup
    rig.create_file("code.py", "def add(a, b):\n    return a - b  # bug: should be +\n")

    # Run
    await rig.run(
        "Fix the bug in code.py - the add function should add, not subtract. "
        "Change 'a - b' to 'a + b'."
    )

    # Assert
    assert rig.tool_was_called("edit_file"), "Agent should call edit_file tool"
