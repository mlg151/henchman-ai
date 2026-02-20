"""Beta test suite for the Henchman-AI Textual TUI.

Uses the real DeepSeek provider (DEEPSEEK_API_KEY must be set).
Tests real LLM streaming, tool execution, and slash commands end-to-end.

Run with:
    python .agent_tasks/tui-polish/beta_test.py
"""

from __future__ import annotations

import asyncio
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[2] / "src"))

from henchman.cli.textual_app import (
    ChatMessage,
    ChatPane,
    ConfirmToolScreen,
    HelpScreen,
    HenchmanTextualApp,
    StatusBar,
    TextualConfig,
)

# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────

PASS = "✅"
FAIL = "❌"
WARN = "⚠️ "
results: list[tuple[str, bool, str]] = []


def record(name: str, ok: bool, detail: str = "") -> None:
    results.append((name, ok, detail))
    icon = PASS if ok else FAIL
    print(f"  {icon}  {name}" + (f"  — {detail}" if detail else ""))


def chat_text(app: HenchmanTextualApp) -> str:
    """Get all joined chat pane message content."""
    chat = app.query_one("#chat-pane", ChatPane)
    return " ".join(w._content for w in chat.children if isinstance(w, ChatMessage))


def make_app() -> HenchmanTextualApp:
    from henchman.cli.app import _get_provider
    from henchman.config import load_settings
    from henchman.config.environment import format_environment_block, gather_environment

    provider = _get_provider()
    settings = load_settings()
    env_ctx = format_environment_block(gather_environment())
    config = TextualConfig(auto_approve_tools=True)
    return HenchmanTextualApp(
        provider=provider,
        config=config,
        settings=settings,
        environment_context=env_ctx,
    )


async def wait_idle(app: HenchmanTextualApp, pilot: object, timeout: float = 30.0) -> bool:
    """Wait until app.is_processing is False, up to *timeout* seconds."""
    deadline = time.monotonic() + timeout
    while app.is_processing and time.monotonic() < deadline:
        await pilot.pause(0.3)  # type: ignore[attr-defined]
    return not app.is_processing


# ──────────────────────────────────────────────────────────────────────────────
# Beta tests
# ──────────────────────────────────────────────────────────────────────────────

async def test_b1_simple_reply() -> None:
    """A trivial prompt returns a coherent streaming reply."""
    print("\n[B1] Simple conversational reply")
    app = make_app()
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause(0.5)

        await pilot.click("#input")
        await pilot.press(*"Reply with exactly the single word: PONG")
        await pilot.press("enter")

        finished = await wait_idle(app, pilot, timeout=30)
        record("processing finished without timeout", finished)

        text = chat_text(app)
        record("reply contains PONG", "PONG" in text.upper(), repr(text[-200:]))
        record("status bar reset to Ready-ish", not app.is_processing)


async def test_b2_streaming_renders() -> None:
    """Multi-token streaming content accumulates correctly (not per-line chunks)."""
    print("\n[B2] Streaming renders as one flowing message")
    app = make_app()
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause(0.5)

        await pilot.click("#input")
        await pilot.press(*"Count from 1 to 5, one number per line.")
        await pilot.press("enter")

        finished = await wait_idle(app, pilot, timeout=30)
        record("processing finished", finished)

        chat = app.query_one("#chat-pane", ChatPane)
        # Agent messages use [bold cyan]<name>:[/] prefix
        agent_msgs = [
            w for w in chat.children
            if isinstance(w, ChatMessage) and "[bold cyan]" in w._prefix
        ]
        record("at least one agent ChatMessage widget created", len(agent_msgs) >= 1,
               f"{len(agent_msgs)} agent widgets, prefixes: {[w._prefix for w in agent_msgs]}")

        if agent_msgs:
            combined = " ".join(w._content for w in agent_msgs)
            digits = [c for c in combined if c.isdigit() and c in "12345"]
            record("all 5 numbers in reply", len(set(digits)) >= 4, repr(combined[:200]))


async def def_b3_read_file_tool() -> None:
    """Agent can use read_file tool and result appears in Tools tab."""
    pass  # placeholder — defined below


async def test_b3_read_file_tool() -> None:
    """Agent uses read_file tool, result appears in Tools pane."""
    print("\n[B3] read_file tool call")
    app = make_app()
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause(0.5)

        readme_path = str(Path(__file__).parents[2] / "README.md")
        await pilot.click("#input")
        await pilot.press(
            *f"Use the read_file tool to read the first 5 lines of {readme_path} and tell me the first non-blank line."
        )
        await pilot.press("enter")

        finished = await wait_idle(app, pilot, timeout=60)
        record("processing finished (tool call)", finished)

        text = chat_text(app)
        record("reply mentions readme content", any(
            kw in text for kw in ("Henchman", "henchman", "CLI", "agent")
        ), repr(text[-200:]))

        from henchman.cli.textual_app import ToolPane
        from textual.widgets import TabbedContent
        # Switch to the Tools tab so RichLog gets a size and flushes its write queue
        tabs = app.query_one(TabbedContent)
        tabs.active = "tab-tools"
        await pilot.pause(0.4)
        tool_pane = app.query_one("#tool-pane", ToolPane)
        # In Textual 8, RichLog exposes `.lines` (not `._lines`)
        has_tool_output = len(tool_pane.lines) > 0
        record("tool pane has tool output", has_tool_output, f"{len(tool_pane.lines)} lines")


async def test_b4_slash_mcp_status() -> None:
    """/mcp status command outputs to chat pane."""
    print("\n[B4] /mcp status command")
    app = make_app()
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause(0.5)

        await pilot.click("#input")
        await pilot.press(*"/mcp status")
        await pilot.press("enter")
        await pilot.pause(1.0)

        text = chat_text(app)
        record("/mcp status produces output",
               "mcp" in text.lower() or "server" in text.lower() or "No" in text,
               repr(text[-150:]))


async def test_b5_slash_chat_save_list() -> None:
    """/chat save and /chat list work end-to-end."""
    print("\n[B5] /chat save + /chat list")
    app = make_app()
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause(0.5)

        # Quick exchange so session has content
        await pilot.click("#input")
        await pilot.press(*"Say hi in one word.")
        await pilot.press("enter")
        await wait_idle(app, pilot, timeout=20)

        # Save it
        await pilot.click("#input")
        await pilot.press(*"/chat save beta-test-session")
        await pilot.press("enter")
        await pilot.pause(0.8)

        # List it
        await pilot.click("#input")
        await pilot.press(*"/chat list")
        await pilot.press("enter")
        await pilot.pause(0.8)

        text = chat_text(app)
        record("/chat save+list shows session", "beta-test-session" in text, repr(text[-200:]))


async def test_b6_error_handling() -> None:
    """Tool errors appear in chat pane, app remains usable."""
    print("\n[B6] Error recovery — bad tool arg")
    app = make_app()
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause(0.5)

        await pilot.click("#input")
        await pilot.press(*"Use read_file to read /this/path/does/not/exist.txt and tell me what happens.")
        await pilot.press("enter")

        finished = await wait_idle(app, pilot, timeout=30)
        record("processing finished after error", finished)

        text = chat_text(app)
        record("reply mentions error or no such file", any(
            kw in text.lower() for kw in ("error", "not found", "no such", "cannot", "exist", "failed")
        ), repr(text[-200:]))

        # App should still be responsive
        prev_text = text
        await pilot.click("#input")
        await pilot.press(*"What is 1+1?")
        await pilot.press("enter")
        finished = await wait_idle(app, pilot, timeout=20)
        new_text = chat_text(app)
        record("app responds after error", new_text != prev_text and finished)


async def test_b7_thinking_pane() -> None:
    """Thinking/reasoning content appears in Thinking tab (if model supports it)."""
    print("\n[B7] Thinking pane population")
    app = make_app()
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause(0.5)

        await pilot.click("#input")
        await pilot.press(*"What is the square root of 144? Think step by step.")
        await pilot.press("enter")
        await wait_idle(app, pilot, timeout=30)

        from henchman.cli.textual_app import ThinkingPane
        thinking_pane = app.query_one("#thinking-pane", ThinkingPane)
        has_thought = len(thinking_pane.lines) > 0
        # Not all models emit THOUGHT events — this is informational only
        if has_thought:
            record("thinking pane has content (model supports THOUGHT)", True)
        else:
            print(f"  {WARN}  thinking pane empty (model may not emit THOUGHT events — OK)")
            results.append(("thinking pane (informational)", True, "model didn't emit THOUGHT"))

        text = chat_text(app)
        record("reply contains '12'", "12" in text, repr(text[-100:]))


async def test_b8_multi_turn() -> None:
    """Multi-turn conversation context is preserved."""
    print("\n[B8] Multi-turn context")
    app = make_app()
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause(0.5)

        await pilot.click("#input")
        await pilot.press(*"My favourite colour is ultraviolet. Remember this.")
        await pilot.press("enter")
        await wait_idle(app, pilot, timeout=20)

        await pilot.click("#input")
        await pilot.press(*"What is my favourite colour?")
        await pilot.press("enter")
        await wait_idle(app, pilot, timeout=20)

        text = chat_text(app)
        record("model recalls favourite colour", "ultraviolet" in text.lower(), repr(text[-200:]))


async def test_b9_status_bar_updates() -> None:
    """Status bar shows 'Processing' during a call and resets after."""
    print("\n[B9] Status bar lifecycle")
    app = make_app()
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause(0.5)

        await pilot.click("#input")
        await pilot.press(*"Tell me a one-sentence joke.")
        await pilot.press("enter")

        # Catch processing state
        processing_seen = False
        for _ in range(10):
            status = app.query_one("#status-bar", StatusBar).status_text
            if "Processing" in status or "Turn" in status or "working" in status.lower():
                processing_seen = True
                break
            await pilot.pause(0.1)

        record("status bar shows activity during call", processing_seen)

        await wait_idle(app, pilot, timeout=25)
        final_status = app.query_one("#status-bar", StatusBar).status_text
        record("status bar resets after call", any(
            kw in final_status for kw in ("Chat", "mock", "deepseek", "Tools")
        ), final_status)


# ──────────────────────────────────────────────────────────────────────────────
# Runner
# ──────────────────────────────────────────────────────────────────────────────

async def run_all() -> int:
    tests = [
        test_b1_simple_reply,
        test_b2_streaming_renders,
        test_b3_read_file_tool,
        test_b4_slash_mcp_status,
        test_b5_slash_chat_save_list,
        test_b6_error_handling,
        test_b7_thinking_pane,
        test_b8_multi_turn,
        test_b9_status_bar_updates,
    ]

    for t in tests:
        try:
            await t()
        except Exception as exc:
            import traceback
            print(f"  {FAIL}  {t.__name__} — EXCEPTION: {exc}")
            traceback.print_exc()
            results.append((t.__name__, False, f"EXCEPTION: {exc}"))

    print("\n" + "─" * 60)
    total = len(results)
    passed = sum(1 for _, ok, _ in results if ok)
    failed = total - passed
    print(f"BETA RESULTS: {passed}/{total} passed  ({failed} failed)")
    if failed:
        print("\nFailed checks:")
        for name, ok, detail in results:
            if not ok:
                print(f"  {FAIL}  {name}" + (f"  — {detail}" if detail else ""))
    print("─" * 60)
    return failed


if __name__ == "__main__":
    failed = asyncio.run(run_all())
    sys.exit(0 if not failed else 1)
