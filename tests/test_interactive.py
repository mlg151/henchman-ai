import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

# Add src to path
sys.path.append(str(Path.cwd() / "src"))

# Mock mcp module to avoid ImportError
mcp_mock = MagicMock()
sys.modules["mcp"] = mcp_mock
sys.modules["mcp.client"] = mcp_mock
sys.modules["mcp.client.stdio"] = mcp_mock
sys.modules["mcp.types"] = mcp_mock
console_mock = MagicMock()

from henchman.cli.input import ToolForm  # noqa: E402
from henchman.cli.input_handler import InputHandler  # noqa: E402
from henchman.cli.repl import ReplConfig  # noqa: E402


def test_tool_form():
    print("Testing ToolForm...")

    # Patch the classes where they are imported in henchman.cli.input
    with (
        patch("henchman.cli.input.Prompt") as prompt_mock,
        patch("henchman.cli.input.Confirm") as confirm_mock,
        patch("henchman.cli.input.IntPrompt") as int_prompt_mock,
    ):
        prompt_mock.ask.return_value = "default_value"
        confirm_mock.ask.return_value = True
        int_prompt_mock.ask.return_value = 42

        form = ToolForm(console_mock)

        params = {
            "properties": {
                "name": {"type": "string", "description": "Name param"},
                "count": {"type": "integer", "description": "Count param"},
                "force": {"type": "boolean", "description": "Force param"},
            },
            "required": ["name"],
        }

        result = form.prompt_for_parameters("test_tool", params)

        if result["name"] != "default_value":
            raise AssertionError(f"String param failed. Got {result['name']}")

        if result["count"] != 42:
            raise AssertionError(f"Integer param failed. Got {result['count']}")

        if not result["force"]:
            raise AssertionError(f"Boolean param failed. Got {result['force']}")

        print("✅ ToolForm parameters collected correctly")


def test_tab_completion():
    print("Testing Tab Completion setup...")

    # Mock create_session to check if completer is passed or set
    with patch("henchman.cli.input_handler.create_session") as create_session_mock:
        session_mock = MagicMock()
        create_session_mock.return_value = session_mock

        handler = InputHandler(ReplConfig(), console_mock)
        handler.initialize_prompt_session()

        # Check if completer was set on session
        if hasattr(session_mock, "completer") and session_mock.completer:
            print("✅ Completer attached to session")
        else:
            raise AssertionError("Completer not attached to session")


if __name__ == "__main__":
    try:
        test_tool_form()
        test_tab_completion()
        sys.exit(0)
    except Exception as e:
        print(f"❌ Exception: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)
