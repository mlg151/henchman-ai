"""Classic transcript rendering modes without a native-terminal qualification claim."""

from io import StringIO

import pytest
from rich.console import Console
from rich.live import Live

from henchman.cli.console import OutputRenderer
from henchman.cli.ui_renderer import UIRenderer


@pytest.mark.parametrize("mode", ["plain", "quiet"])
def test_plain_rendering_is_literal_and_does_not_mutate_callers_console(mode):
    stream = StringIO()
    original = Console(file=stream, force_terminal=True, color_system="truecolor", width=40)
    renderer = OutputRenderer(console=original, output_mode=mode)
    link = "https://example.invalid/" + "long-path/" * 20
    renderer.markdown(f"## Heading\n[long link]({link})\n```python\nx = '[bold]literal[/bold]'\n```")
    renderer.code("x = '[bold]literal[/bold]'\n")
    renderer.diff("old\n", "new\n", "example.py")
    renderer.warning("warning stays")
    renderer.error("error stays")
    renderer.info("explicit status stays")
    renderer.muted("explicit command output stays")
    renderer.table([{"state": "Unknown", "target": "file.py"}])
    output = stream.getvalue()
    assert "\x1b" not in output
    assert f"[long link]({link})" in output
    assert "x = '[bold]literal[/bold]'" in output
    assert "--- a/example.py" in output and "+new" in output
    assert "[WARN] warning stays" in output
    assert "[ERR] error stays" in output
    assert "[INFO] explicit status stays" in output
    assert "explicit command output stays" in output and "Unknown" in output
    assert original.is_terminal and original.color_system == "truecolor"
    assert renderer.console is not original


@pytest.mark.parametrize("mode", ["plain", "quiet"])
def test_status_and_progress_have_no_live_refresh(mode, monkeypatch):
    def forbidden_start(*_args, **_kwargs):
        raise AssertionError("Transcript mode must not start a Live display")

    monkeypatch.setattr(Live, "start", forbidden_start)
    stream = StringIO()
    ui = UIRenderer(console=Console(file=stream, force_terminal=True), output_mode=mode)
    ui.print_welcome()
    ui.start_thinking("work detail")
    assert ui.is_thinking
    ui.stop_thinking()
    assert not ui.is_thinking
    with ui.create_status("indexing") as status:
        status.update("more indexing")
    progress = ui.start_task("task", "copying", 10)
    ui.update_task("task", advance=3)
    assert progress.tasks[0].completed == 3
    ui.complete_task("task")
    assert not ui.progress_manager.tasks
    ui.print_goodbye()
    output = stream.getvalue()
    assert "\x1b" not in output
    if mode == "quiet":
        assert output == ""
    else:
        assert "work detail" in output and "copying" in output
        assert "indexing" in output


def test_default_rich_rendering_remains_styled():
    stream = StringIO()
    console = Console(file=stream, force_terminal=True, color_system="standard", no_color=False)
    renderer = OutputRenderer(console=console)
    renderer.warning("same rich warning")
    assert renderer.console is console
    assert "\x1b" in stream.getvalue()


@pytest.mark.parametrize("mode", ["plain", "quiet"])
def test_explicit_renderer_actions_remain_visible(mode):
    stream = StringIO()
    ui = UIRenderer(console=Console(file=stream), output_mode=mode)
    ui.success("OAuth status: ready")
    ui.tool_result("explicit inspection result")
    ui.console.print("usage: unknown cost", markup=False)
    ui.heading("Configuration")
    ui.rule("Requested details")
    output = stream.getvalue()
    for text in ("OAuth status: ready", "explicit inspection result", "usage: unknown cost", "Configuration", "Requested details"):
        assert text in output


@pytest.mark.parametrize("mode", ["plain", "quiet"])
def test_transcript_console_follows_stdout_replacement(mode, monkeypatch):
    import sys

    original_stream, patched_stream = StringIO(), StringIO()
    monkeypatch.setattr(sys, "stdout", original_stream)
    source = Console()
    renderer = OutputRenderer(console=source, output_mode=mode)
    monkeypatch.setattr(sys, "stdout", patched_stream)
    renderer.info("goes through patched stdout")
    assert "goes through patched stdout" in patched_stream.getvalue()
    assert not original_stream.getvalue()
    local_stream = StringIO()
    renderer.console.file = local_stream
    renderer.info("local replacement")
    assert "local replacement" in local_stream.getvalue()
    assert "local replacement" not in patched_stream.getvalue()
    assert source.file is patched_stream


def test_wrapped_plain_renderer_keeps_its_destination():
    stream = StringIO()
    renderer = OutputRenderer(console=Console(file=stream), output_mode="plain")
    ui = UIRenderer(renderer=renderer)
    ui.print_welcome()
    assert ui.console is renderer.console
    assert "Henchman-AI" in stream.getvalue()
