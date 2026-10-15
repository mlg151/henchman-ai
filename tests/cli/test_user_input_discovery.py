"""Registration alone cannot establish that user input is connected."""

from henchman.cli.commands.discovery_capabilities import (
    build_discovery_capabilities,
    classify_registered_tool,
)


def test_help_reports_input_channel_dependency():
    capabilities = build_discovery_capabilities(registered_tool_names=("ask_user",))
    capability = next(item for item in capabilities if item.name == "ask_user")
    assert capability.classification == "runtime-dependent"
    assert "REPL" in capability.summary
    assert "headless" in capability.detail


def test_registered_question_tool_does_not_imply_interactive_answers():
    capability = classify_registered_tool("ask_user", registered_tool_names=("ask_user",))
    assert capability is not None
    assert capability.classification == "runtime-dependent"
    assert "handler" in capability.detail


def test_missing_question_tool_is_unavailable():
    capabilities = build_discovery_capabilities()
    capability = next(item for item in capabilities if item.name == "ask_user")
    assert capability.classification == "unavailable"
