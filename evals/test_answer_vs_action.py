"""Behavioral evals for answer vs. action decisions.

These tests verify that the agent correctly decides when to take action
versus when to just answer a question. Tests run against REAL LLM providers.
"""

from evals.helpers import eval_test


@eval_test("USUALLY_PASSES")
async def test_answers_question_without_editing(rig) -> None:
    """Agent should answer questions about code without modifying it."""
    # Setup
    rig.create_file(
        "app.py",
        "def calculate(a, b):\n    return a - b  # Subtraction\n",
    )

    # Run - ask a question, don't request a change
    await rig.run("What does the calculate function in app.py do? Just explain it.")

    # Assert: Should read the file but NOT edit it
    assert rig.tool_was_called("read_file"), "Agent should read the file"
    assert not rig.tool_was_called("edit_file"), "Agent should not edit when just asked a question"
    assert not rig.tool_was_called("write_file"), (
        "Agent should not write when just asked a question"
    )


@eval_test("USUALLY_PASSES")
async def test_does_not_auto_fix_when_inspecting(rig) -> None:
    """Agent should not automatically fix issues when asked to inspect/review."""
    # Setup
    rig.create_file(
        "buggy.py",
        "def add(a, b):\n    return a - b  # This is obviously wrong!\n",
    )

    # Run - ask to inspect, not to fix
    await rig.run("Review buggy.py and tell me if there are any issues.")

    # Assert: Should identify but not fix (unless explicitly asked)
    assert not rig.tool_was_called("edit_file"), "Agent should ask before fixing"
    assert not rig.tool_was_called("write_file"), "Agent should ask before modifying"


@eval_test("ALWAYS_PASSES")
async def test_edits_when_explicitly_asked_to_fix(rig) -> None:
    """Agent should edit files when explicitly asked to fix something."""
    # Setup
    rig.create_file(
        "broken.py",
        "def multiply(a, b):\n    return a + b  # Wrong: should multiply\n",
    )

    # Run - explicitly ask to fix
    await rig.run("Fix the bug in broken.py - multiply should use * not +. Make the change now.")

    # Assert: Should fix when asked
    assert rig.tool_was_called("edit_file") or rig.tool_was_called("write_file"), (
        "Agent should edit when asked to fix"
    )


@eval_test("USUALLY_PASSES")
async def test_asks_clarification_on_ambiguous_request(rig) -> None:
    """Agent should ask for clarification when request is ambiguous."""
    # Setup - multiple files, unclear which one to modify
    rig.create_file("config1.yaml", "setting: value1")
    rig.create_file("config2.yaml", "setting: value2")
    rig.create_file("config3.yaml", "setting: value3")

    # Run - ambiguous request
    result = await rig.run("Update the config file.")

    # Assert: Should not modify anything without clarification
    # Either asks which file, or doesn't modify any
    if not rig.tool_was_called("ask_user"):
        # If it didn't ask, it should at least not have blindly edited
        edit_calls = rig.get_tool_calls("edit_file") + rig.get_tool_calls("write_file")
        # Allow at most one file to be modified (if agent made a reasonable guess)
        assert len(edit_calls) <= 1, "Agent should not modify multiple files without clarification"


@eval_test("USUALLY_PASSES")
async def test_reads_before_editing(rig) -> None:
    """Agent should read a file before editing it (to understand context)."""
    # Setup
    rig.create_file(
        "module.py",
        "class Calculator:\n"
        "    def add(self, a, b):\n"
        "        return a + b\n"
        "\n"
        "    def subtract(self, a, b):\n"
        "        return a - b\n",
    )

    # Run - ask to add a method
    await rig.run("Add a multiply method to the Calculator class in module.py.")

    # Assert: Should read first to understand the class structure
    all_calls = rig.get_all_tool_calls()
    tool_names = [call.tool_name for call in all_calls]

    assert "read_file" in tool_names, "Agent should read the file first"

    # read_file should come before edit_file
    if "edit_file" in tool_names:
        read_idx = tool_names.index("read_file")
        edit_idx = tool_names.index("edit_file")
        assert read_idx < edit_idx, "Agent should read before editing"
