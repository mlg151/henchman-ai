"""JSON consumers receive complete frames independent of terminal formatting."""

import io
import json

import pytest
from rich.console import Console

from henchman.cli.json_output import JsonOutputRenderer
from henchman.core.events import AgentEvent, EventType


@pytest.mark.parametrize("width", [20, 80])
@pytest.mark.parametrize("method", ["render", "render_stream_json"])
@pytest.mark.parametrize(
    "content", ["x" * 512, "中文 e\u0301 😀 :rocket: [bold]plain[/bold]\n" * 16 + "!"],
    ids=["long_ascii", "unicode_literal_markup"],
)
def test_jsonl_stdout_has_one_parseable_line_per_event(width: int, method: str, content: str) -> None:
    output = io.StringIO()
    console = Console(file=output, width=width, force_terminal=False, color_system=None)
    renderer = JsonOutputRenderer(console)
    events = [
        AgentEvent(EventType.CONTENT, content, source_agent="worker"),
        AgentEvent(EventType.FINISHED, {"finish_reason": "stop"}, source_agent="orchestrator"),
    ]

    for event in events:
        getattr(renderer, method)(event)

    frames = output.getvalue().splitlines()
    assert len(frames) == 2
    assert json.loads(frames[0]) == {"type": "content", "source_agent": "worker", "data": content}
    assert json.loads(frames[1]) == {
        "type": "finished", "source_agent": "orchestrator", "task_verified": False,
        "data": {"finish_reason": "stop"},
    }
    assert events[0].data == content


@pytest.mark.parametrize("width", [20, 80])
def test_complete_json_stdout_preserves_long_nested_unicode_payload(width: int) -> None:
    output = io.StringIO()
    renderer = JsonOutputRenderer(Console(file=output, width=width, force_terminal=False, color_system=None))
    arguments = {"path": "目录/" + "long-name-" * 32 + ".py", "content": ":rocket: 😀\n" * 64}
    event = AgentEvent(EventType.TOOL_CALL_REQUEST, {"id": "call", "name": "write_file", "arguments": arguments})

    renderer.render_final_json([event])

    assert json.loads(output.getvalue()) == [{"type": "tool_call_request", "data": event.data}]
    assert event.data["arguments"] == arguments
