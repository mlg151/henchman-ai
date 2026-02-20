"""Alpha test suite for the Henchman-AI Textual TUI.

Run with:
    python .agent_tasks/tui-polish/alpha_test.py

Uses Textual's run_test (headless Pilot) so no real terminal / TTY is required.
All LLM calls are intercepted by a mock provider.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock

# Make sure the project src is importable
sys.path.insert(0, str(Path(__file__).parents[2] / "src"))

from henchman.cli.textual_app import (
    ChatMessage,
    ChatPane,
    ConfirmToolScreen,
    HelpScreen,
    HenchmanTextualApp,
    ProviderScreen,
    StatusBar,
    TextualConfig,
)
from henchman.core.events import AgentEvent, EventType
from henchman.providers.base import ModelProvider, StreamChunk, Message, FinishReason

# ──────────────────────────────────────────────────────────────────────────────
# Mock provider
# ──────────────────────────────────────────────────────────────────────────────

class MockProvider(ModelProvider):
    """Minimal mock provider that streams a fixed reply."""

    name = "mock"
    model = "mock-model"

    def __init__(self, reply: str = "Hello from mock!") -> None:
        self._reply = reply

    async def chat_completion_stream(self, messages: list[Message], **kwargs: Any):  # type: ignore[override]
        for word in self._reply.split():
            yield StreamChunk(content=word + " ")
            await asyncio.sleep(0)
        yield StreamChunk(content="", finish_reason=FinishReason.STOP)


# ──────────────────────────────────────────────────────────────────────────────
# Test helpers
# ──────────────────────────────────────────────────────────────────────────────

PASS = "✅"
FAIL = "❌"
results: list[tuple[str, bool, str]] = []


def record(name: str, ok: bool, detail: str = "") -> None:
    results.append((name, ok, detail))
    icon = PASS if ok else FAIL
    print(f"  {icon}  {name}" + (f"  — {detail}" if detail else ""))


def make_app(reply: str = "Hello from mock!") -> HenchmanTextualApp:
    provider = MockProvider(reply)
    config = TextualConfig(auto_approve_tools=True)
    return HenchmanTextualApp(provider=provider, config=config, settings=None)


# ──────────────────────────────────────────────────────────────────────────────
# Tests
# ──────────────────────────────────────────────────────────────────────────────

async def test_launch_welcome() -> None:
    """TUI launches without error and shows welcome messages."""
    print("\n[1] Launch & welcome banner")
    app = make_app()
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause(0.5)

        # Check welcome messages are in the chat pane
        chat = app.query_one("#chat-pane", ChatPane)
        all_text = " ".join(w._content for w in chat.children if isinstance(w, ChatMessage))

        record("welcome banner present", "Henchman-AI" in all_text, repr(all_text[:100]))
        record("keybindings hint present", "help" in all_text.lower(), repr(all_text[:200]))

        # Status bar should have provider info
        status = app.query_one("#status-bar", StatusBar)
        record("status bar shows provider", "mock" in status.status_text.lower(), status.status_text)

        # Input widget should be focused
        from textual.widgets import TextArea
        try:
            input_widget = app.query_one("#input", TextArea)
            record("input widget exists", True)
        except Exception as exc:
            record("input widget exists", False, str(exc))


async def test_slash_help_command() -> None:
    """Typing /help produces visible output in the chat pane."""
    print("\n[2] /help command")
    app = make_app()
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause(0.3)
        await pilot.press("slash")
        await pilot.press(*"help")
        await pilot.press("enter")
        await pilot.pause(0.5)

        chat = app.query_one("#chat-pane", ChatPane)
        all_text = " ".join(w._content for w in chat.children if isinstance(w, ChatMessage))
        record("/help produces output", len(all_text) > 50, repr(all_text[:120]))


async def test_slash_tools_command() -> None:
    """Typing /tools produces a tool list."""
    print("\n[3] /tools command")
    app = make_app()
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause(0.3)
        await pilot.press("slash")
        await pilot.press(*"tools")
        await pilot.press("enter")
        await pilot.pause(0.5)

        chat = app.query_one("#chat-pane", ChatPane)
        all_text = " ".join(w._content for w in chat.children if isinstance(w, ChatMessage))
        record("/tools produces output", len(all_text) > 20, repr(all_text[:120]))


async def test_slash_clear_command() -> None:
    """/clear removes messages from chat pane."""
    print("\n[4] /clear command")
    app = make_app()
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause(0.3)
        # First confirm there are welcome messages
        chat = app.query_one("#chat-pane", ChatPane)
        count_before = len(list(chat.children))
        record("messages present before clear", count_before > 0, f"{count_before} messages")

        await pilot.press("slash")
        await pilot.press(*"clear")
        await pilot.press("enter")
        await pilot.pause(0.3)

        count_after = len(list(chat.children))
        # After TUI-native /clear, all messages should be gone
        record("/clear removes messages", count_after == 0, f"before={count_before} after={count_after}")


async def test_command_palette() -> None:
    """Typing / shows the command palette."""
    print("\n[5] Command palette")
    app = make_app()
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause(0.3)
        from textual.widgets import OptionList
        palette = app.query_one("#command-palette", OptionList)
        record("palette hidden initially", not palette.display)

        await pilot.press("slash")
        await pilot.pause(0.2)
        record("palette visible after /", palette.display, f"display={palette.display}")
        record("palette has options", palette.option_count > 0, f"count={palette.option_count}")

        await pilot.press("escape")
        await pilot.pause(0.1)


async def test_help_modal() -> None:
    """F1 opens the help modal."""
    print("\n[6] Help modal (F1)")
    app = make_app()
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause(0.3)
        await pilot.press("f1")
        await pilot.pause(0.3)

        # push_screen makes HelpScreen the active screen
        record("HelpScreen is active screen", isinstance(app.screen, HelpScreen))
        if not isinstance(app.screen, HelpScreen):
            return

        await pilot.press("escape")
        await pilot.pause(0.1)
        record("HelpScreen dismissed by escape", not isinstance(app.screen, HelpScreen))


async def test_provider_modal() -> None:
    """F2 opens the provider switching modal."""
    print("\n[7] Provider modal (F2)")
    app = make_app()
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause(0.3)
        await pilot.press("f2")
        await pilot.pause(0.3)

        # push_screen makes ProviderScreen the active screen
        record("ProviderScreen is active screen", isinstance(app.screen, ProviderScreen))
        if not isinstance(app.screen, ProviderScreen):
            return

        # Click Cancel button
        from textual.widgets import Button
        cancel_btns = [b for b in app.screen.query(Button) if "cancel" in str(b.id).lower()]
        if cancel_btns:
            await pilot.click(f"#{cancel_btns[0].id}")
            await pilot.pause(0.2)
        else:
            await pilot.press("escape")
            await pilot.pause(0.2)

        record("ProviderScreen dismissed", not isinstance(app.screen, ProviderScreen))


async def test_streaming_content() -> None:
    """Submitting a prompt streams reply into the chat pane."""
    print("\n[8] Streaming content")
    app = make_app("Hello from the mock provider!")
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause(0.3)

        from textual.widgets import TextArea
        input_widget = app.query_one("#input", TextArea)
        await pilot.click("#input")
        await pilot.press(*"what is 2 plus 2")
        await pilot.press("enter")

        # Wait for processing to finish (up to 5 s)
        for _ in range(50):
            await pilot.pause(0.1)
            if not app.is_processing:
                break

        chat = app.query_one("#chat-pane", ChatPane)
        all_text = " ".join(w._content for w in chat.children if isinstance(w, ChatMessage))

        record("user message appears in chat", "2 plus 2" in all_text, repr(all_text[:100]))
        record("assistant reply streams in", "Hello" in all_text and "mock" in all_text.lower(), repr(all_text[:200]))
        record("processing flag reset", not app.is_processing)


async def test_history_navigation() -> None:
    """Arrow-up navigates command history."""
    print("\n[9] History navigation")
    app = make_app()
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause(0.3)

        # Submit a command so it's in history
        await pilot.press("slash")
        await pilot.press(*"clear")
        await pilot.press("enter")
        await pilot.pause(0.3)

        # Navigate up
        from textual.widgets import TextArea
        await pilot.click("#input")
        await pilot.press("up")
        await pilot.pause(0.1)
        input_widget = app.query_one("#input", TextArea)
        record("up arrow fills history", len(input_widget.text) > 0, repr(input_widget.text))

        # Navigate down (should clear)
        await pilot.press("down")
        await pilot.pause(0.1)
        record("down arrow clears history", input_widget.text == "", repr(input_widget.text))


async def test_context_tree() -> None:
    """Context tab Tree is populated (or shows a leaf if no files found)."""
    print("\n[10] Context tree")
    app = make_app()
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause(0.5)

        try:
            from textual.widgets import Tree
            tree = app.query_one("#context-tree", Tree)
            # Tree root should have at least one child (file or "No context files found")
            children = list(tree.root.children)
            record("context tree populated", len(children) > 0, f"{len(children)} children")
        except Exception as exc:
            record("context tree populated", False, str(exc))


async def test_tool_confirmation_modal() -> None:
    """ConfirmToolScreen renders correctly and both buttons work."""
    print("\n[11] Tool confirmation modal")
    from henchman.tools.base import ConfirmationRequest

    req = ConfirmationRequest(
        tool_name="write_file",
        description="Write content to a file",
        params={"path": "/tmp/test.txt", "content": "hello"},
        risk_level="medium",
    )

    app = make_app()
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause(0.3)

        # Push the confirm screen directly
        result_holder: list[bool | None] = [None]

        def capture(r: bool | None) -> None:
            result_holder[0] = r

        app.push_screen(ConfirmToolScreen(req), capture)
        await pilot.pause(0.3)

        # push_screen makes ConfirmToolScreen the active screen
        record("ConfirmToolScreen is active screen", isinstance(app.screen, ConfirmToolScreen))
        if not isinstance(app.screen, ConfirmToolScreen):
            return

        # Click Yes
        from textual.widgets import Button
        await pilot.click("#btn-yes")
        await pilot.pause(0.2)
        record("Yes returns True", result_holder[0] is True, str(result_holder[0]))

        # Re-push and click No (use keyboard shortcut 'n' to avoid click targeting issues)
        result_holder[0] = None
        app.push_screen(ConfirmToolScreen(req), capture)
        await pilot.pause(0.5)  # give Textual time to mount the second screen
        record("ConfirmToolScreen re-mounted for No test", isinstance(app.screen, ConfirmToolScreen))
        await pilot.press("n")   # ConfirmToolScreen binding: ("n", "deny", "No")
        await pilot.pause(0.3)
        record("No / deny returns False", result_holder[0] is False, str(result_holder[0]))


async def test_search_mode() -> None:
    """Ctrl+F enters search mode and F3 navigates matches."""
    print("\n[12] Search mode")
    app = make_app()
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause(0.3)

        record("search mode off initially", not app._search_mode)

        await pilot.press("ctrl+f")
        await pilot.pause(0.1)
        record("ctrl+f enters search mode", app._search_mode)

        # Type a query
        from textual.widgets import TextArea
        await pilot.click("#input")
        await pilot.press(*"Henchman")
        await pilot.pause(0.1)

        # Press F3 to search
        await pilot.press("f3")
        await pilot.pause(0.1)
        status = app.query_one("#status-bar", StatusBar)
        record("search status updates", "Henchman" in status.status_text or "match" in status.status_text.lower() or "No match" in status.status_text, status.status_text)

        # Escape clears search mode
        await pilot.press("escape")
        await pilot.pause(0.1)
        record("escape clears search mode", not app._search_mode)


async def test_chat_message_streaming() -> None:
    """ChatPane.begin_agent_stream / append_agent_chunk / finish_agent_stream works."""
    print("\n[13] ChatPane streaming unit")
    app = make_app()
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause(0.3)

        chat = app.query_one("#chat-pane", ChatPane)
        widget = chat.begin_agent_stream("TestAgent")
        await pilot.pause(0.1)

        record("begin_agent_stream creates widget", widget in chat._active.values())

        chat.append_agent_chunk("TestAgent", "chunk1 ")
        chat.append_agent_chunk("TestAgent", "chunk2")
        await pilot.pause(0.1)

        record("chunks accumulate in widget", "chunk1 chunk2" in widget._content, repr(widget._content))

        chat.finish_agent_stream("TestAgent")
        record("finish removes from active", "TestAgent" not in chat._active)


async def test_no_tui_on_plain_import() -> None:
    """The lazy ``__getattr__`` in app.py avoids importing Textual at module level
    (import-time penalty check — static analysis only)."""
    print("\n[14] No top-level Textual import in app.py")
    app_src = Path("src/henchman/cli/app.py").read_text()
    # Confirm the lazy pattern is present (textual import inside __getattr__)
    has_getattr_guard = "__getattr__" in app_src and "textual_app" in app_src
    # Reject bare top-level imports OUTSIDE `__getattr__`
    import ast
    try:
        tree = ast.parse(app_src)
        top_level_textual = [
            node for node in ast.walk(tree)
            if isinstance(node, (ast.Import, ast.ImportFrom))
            and isinstance(getattr(node, 'module', '') or '', str)
            and 'textual' in (getattr(node, 'module', '') or '')
        ]
        # All textual imports must be inside function/method bodies (not at module level)
        module_level_nodes = {id(n) for n in ast.walk(tree)
                              if isinstance(n, (ast.Import, ast.ImportFrom))}
        func_body_nodes = set()
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                for child in ast.walk(node):
                    if isinstance(child, (ast.Import, ast.ImportFrom)):
                        func_body_nodes.add(id(child))
        bare_textual = [
            n for n in top_level_textual if id(n) not in func_body_nodes
        ]
        record(
            "No bare top-level textual import in app.py",
            len(bare_textual) == 0,
            f"{len(bare_textual)} bare import(s) found",
        )
    except SyntaxError as exc:
        record("No bare top-level textual import in app.py", False, str(exc))


# ──────────────────────────────────────────────────────────────────────────────
# Runner
# ──────────────────────────────────────────────────────────────────────────────

async def run_all() -> None:
    tests = [
        test_launch_welcome,
        test_slash_help_command,
        test_slash_tools_command,
        test_slash_clear_command,
        test_command_palette,
        test_help_modal,
        test_provider_modal,
        test_streaming_content,
        test_history_navigation,
        test_context_tree,
        test_tool_confirmation_modal,
        test_search_mode,
        test_chat_message_streaming,
        test_no_tui_on_plain_import,
    ]

    for t in tests:
        try:
            await t()
        except Exception as exc:
            import traceback
            print(f"  ❌  {t.__name__} — EXCEPTION: {exc}")
            traceback.print_exc()
            results.append((t.__name__, False, f"EXCEPTION: {exc}"))

    # ── summary ──────────────────────────────────────────────────────────────
    print("\n" + "─" * 60)
    total = len(results)
    passed = sum(1 for _, ok, _ in results if ok)
    failed = total - passed
    print(f"RESULTS: {passed}/{total} passed  ({failed} failed)")
    if failed:
        print("\nFailed checks:")
        for name, ok, detail in results:
            if not ok:
                print(f"  ❌  {name}" + (f"  — {detail}" if detail else ""))
    print("─" * 60)
    return failed


if __name__ == "__main__":
    failed = asyncio.run(run_all())
    sys.exit(0 if not failed else 1)
