"""Replay two synthetic failures against a fixed loopback model; never run its tools."""

from __future__ import annotations

import hashlib
import http.client
import json
import os
import sys
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent
PLAN = ROOT / "plan.json"
ID = "task-ece01189221b"
OLD = '    print(f"Hello, {name}!"\n    return True'
NEW = '    print(f"Hello, {name}!")\n    return True'
FILE = '\ndef greet(name):\n    print(f"Hello, {name}!"\n    return True\n'
ERRORS = {
    "unmatched-edit": {
        "baseline": 'Error: String not found in file:     print(f"Hello, {name}"\n    return True...',
        "candidate": "Error: String not found in file. The file was not changed. Reread the current file with read_file and copy the exact text into old_str before retrying. Do not guess line ranges or combine old_str with start_line/end_line.",
    },
    "incomplete-task-id": {
        "baseline": "'Task ece01189221b not found.'",
        "candidate": "Task not found. Use task_list for current project IDs and retry with the exact ID, including the task- prefix.",
    },
}


def tool(name: str, description: str, properties: dict[str, Any], required: list[str]) -> dict[str, Any]:
    return {"type": "function", "function": {"name": name, "description": description,
            "parameters": {"type": "object", "properties": properties, "required": required}}}


def call(name: str, arguments: dict[str, Any], identity: str) -> dict[str, Any]:
    return {"role": "assistant", "content": None, "tool_calls": [{"id": identity, "type": "function",
            "function": {"name": name, "arguments": json.dumps(arguments)}}]}


def response(identity: str, content: str) -> dict[str, str]:
    return {"role": "tool", "tool_call_id": identity, "content": content}


def request(case: str, arm: str, plan: dict[str, Any]) -> dict[str, Any]:
    messages: list[dict[str, Any]] = [{"role": "system", "content": "You are a coding assistant. Use the available tools to continue the task. /no_think"}]
    if case == "unmatched-edit":
        messages += [
            {"role": "user", "content": "Fix the syntax error in broken.py and retain its behavior."},
            call("read_file", {"path": "broken.py"}, "read1"), response("read1", FILE),
            call("edit_file", {"path": "broken.py", "old_str": '    print(f"Hello, {name}"\n    return True', "new_str": NEW}, "edit1"),
            response("edit1", ERRORS[case][arm]),
        ]
        tools = [tool("read_file", "Read a file", {"path": {"type": "string"}}, ["path"]),
                 tool("edit_file", "Replace exact text in a file", {"path": {"type": "string"}, "old_str": {"type": "string"}, "new_str": {"type": "string"}}, ["path", "old_str", "new_str"])]
    else:
        messages += [
            {"role": "user", "content": "Inspect the output of the Python verification task."},
            call("python_exec", {"code": "print('compile OK')"}, "run1"),
            response("run1", f"Started background task {ID} [running]. Use task_get for status, task_output for output, task_list for all jobs, or task_stop to stop this task. Starting a task does not confirm success."),
            call("task_output", {"task_id": ID.removeprefix("task-")}, "output1"), response("output1", ERRORS[case][arm]),
        ]
        tools = [tool("task_list", "List tasks for the current project", {}, []),
                 tool("task_output", "Read captured task output", {"task_id": {"type": "string"}}, ["task_id"])]
    return {"model": plan["model"], "messages": messages, "tools": tools, "tool_choice": "auto",
            "temperature": plan["temperature"], "max_tokens": plan["max_tokens"], "stream": False,
            "chat_template_kwargs": {"enable_thinking": False}}


def accepted(case: str, data: Any) -> bool:
    try:
        calls = data["choices"][0]["message"]["tool_calls"]
        if len(calls) != 1:
            return False
        function = calls[0]["function"]
        args = json.loads(function["arguments"])
        if not isinstance(args, dict):
            return False
        name = function["name"]
        if case == "unmatched-edit":
            return (name == "read_file" and args == {"path": "broken.py"}) or (
                name == "edit_file" and args == {"path": "broken.py", "old_str": OLD, "new_str": NEW})
        return (name == "task_list" and args == {}) or (name == "task_output" and args == {"task_id": ID})
    except (KeyError, TypeError, ValueError, IndexError):
        return False


def main() -> int:
    if len(sys.argv) != 2:
        raise SystemExit("usage: run.py PRIVATE_OUTPUT_JSON")
    destination = Path(sys.argv[1])
    descriptor = os.open(destination, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    os.close(descriptor)
    plan_bytes = PLAN.read_bytes()
    plan = json.loads(plan_bytes)
    receipt: dict[str, Any] = {"plan_sha256": hashlib.sha256(plan_bytes).hexdigest(),
        "runner_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "planned": len(plan["order"]), "observations": []}
    for case, arm, repeat in plan["order"]:
        body = json.dumps(request(case, arm, plan), separators=(",", ":")).encode()
        row: dict[str, Any] = {"case": case, "arm": arm, "repeat": repeat,
                               "request_sha256": hashlib.sha256(body).hexdigest(), "accepted": False}
        started = time.monotonic()
        connection = http.client.HTTPConnection("127.0.0.1", 8082, timeout=plan["timeout_seconds"])
        try:
            connection.request("POST", "/v1/chat/completions", body, {"Content-Type": "application/json"})
            result = connection.getresponse()
            raw = result.read(1_000_001)
            row.update(status=result.status, response_sha256=hashlib.sha256(raw).hexdigest())
            if len(raw) > 1_000_000:
                raise ValueError("response exceeds bound")
            data = json.loads(raw)
            row["response"] = data
            row["accepted"] = result.status == 200 and data.get("model") == plan["model"] and accepted(case, data)
        except (OSError, TimeoutError, ValueError, http.client.HTTPException) as exc:
            row["error"] = type(exc).__name__
        finally:
            connection.close()
            row["duration_seconds"] = time.monotonic() - started
            receipt["observations"].append(row)
            temporary = destination.with_suffix(".partial")
            temporary.write_text(json.dumps(receipt, indent=2) + "\n")
            os.chmod(temporary, 0o600)
            os.replace(temporary, destination)
        print(json.dumps({key: row.get(key) for key in ("case", "arm", "repeat", "status", "accepted", "error")}), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
