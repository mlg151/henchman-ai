"""Actual supported Neovim subprocess pilot; scripted pipes and owned HTTP only."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import threading
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from importlib.resources import files

import pytest


@pytest.fixture
def nvim():
    binary = os.environ.get("HENCHMAN_TEST_NVIM") or shutil.which("nvim")
    if not binary:
        pytest.skip("Set HENCHMAN_TEST_NVIM to the qualified Neovim 0.12.6 binary")
    version = subprocess.run([binary, "--version"], capture_output=True, text=True, timeout=10, check=True)
    if not version.stdout.startswith("NVIM v0.12.6\n") or sys.platform != "linux":
        pytest.skip("Pilot qualification is Neovim 0.12.6 on Linux")
    return binary


def run_lua(nvim, tmp_path, body, *, timeout=20):
    module = str(files("henchman.integrations").joinpath("neovim.lua"))
    script = tmp_path / "pilot.lua"
    completed = tmp_path / "pilot-completed"
    completed.unlink(missing_ok=True)
    script.write_text(
        "local pilot = dofile(" + json.dumps(module) + ")\n" + body
        + "\nvim.fn.writefile({\"complete\"}, " + json.dumps(str(completed)) + ")\n"
    )
    result = subprocess.run([nvim, "--headless", "-u", "NONE", "-l", str(script)],
                            cwd=tmp_path, capture_output=True, text=True, timeout=timeout, check=False)
    assert result.returncode == 0, result.stdout + result.stderr
    assert completed.exists(), "Neovim script did not finish"
    assert completed.read_text() == "complete\n", "Neovim completion marker is invalid"
    return result


def fake_server(tmp_path, body):
    script = tmp_path / "server.py"
    script.write_text("import json,sys,time\n" + body)
    return [sys.executable, str(script)]


def options(tmp_path, command, **extra):
    (tmp_path / "selected.py").write_text("value = 1\n")
    return json.dumps({"project": str(tmp_path), "paths": ["selected.py"], "command": command,
                       "session": {"mode": "new"}, "prompt": "inspect selection", **extra})


def test_editor_early_zero_exit_cannot_pass_unfinished_script(nvim, tmp_path):
    with pytest.raises(AssertionError, match="did not finish"):
        run_lua(nvim, tmp_path, 'vim.cmd("qa!")\nerror("never reached")\n')


def test_no_implicit_session_and_unsaved_buffer_refusal(nvim, tmp_path):
    opts = options(tmp_path, ["must-not-launch"])
    run_lua(nvim, tmp_path, f'''
local opts = vim.json.decode({json.dumps(opts)})
pilot.setup({{command=opts.command, project=opts.project}})
assert(pilot.status() == nil)
vim.cmd.edit("selected.py")
vim.api.nvim_buf_set_lines(0, 0, -1, false, {{"unsaved user text"}})
local ok, reason = pilot.run(opts)
assert(not ok and reason:find("Unsaved", 1, true))
assert(vim.bo.modified and vim.bo.modifiable)
assert(vim.api.nvim_get_current_line() == "unsaved user text")
opts.session = nil
ok, reason = pilot.run(opts)
assert(not ok and reason:find("session", 1, true))
''')


def test_missing_executable_restores_options_and_leaves_no_active_owner(nvim, tmp_path):
    opts = options(tmp_path, ["must-not-launch"])
    run_lua(nvim, tmp_path, f'''
vim.cmd.edit("selected.py")
local ok, reason = pilot.run(vim.json.decode({json.dumps(opts)}))
assert(not ok and reason:find("start",1,true))
assert(vim.bo.modifiable and pilot.status().settled)
''')


def test_newly_opened_selected_buffer_is_held_and_original_readonly_option_restored(nvim, tmp_path):
    opts = options(tmp_path, decision_server(tmp_path))
    run_lua(nvim, tmp_path, f'''
local callback
vim.ui.select = function(_, _, reply) callback=reply end
assert(pilot.run(vim.json.decode({json.dumps(opts)})))
assert(vim.wait(8000, function() return callback ~= nil end, 10))
vim.cmd.edit("selected.py")
assert(not vim.bo.modifiable)
callback("Deny")
assert(vim.wait(8000, function() return pilot.status().settled end, 10))
assert(vim.bo.modifiable)
vim.bo.modifiable=false
callback=nil
assert(pilot.run(vim.json.decode({json.dumps(opts)})))
assert(vim.wait(8000, function() return callback ~= nil end, 10))
callback("Deny")
assert(vim.wait(8000, function() return pilot.status().settled end, 10))
assert(not vim.bo.modifiable)
''')


def test_resume_response_cannot_silently_bind_another_session(nvim, tmp_path):
    body = '''
first=json.loads(sys.stdin.readline())
assert first["params"]["session"] == {"mode":"resume","id":"chosen-session"}
frame={"v":1,"seq":1,"kind":"response","request_id":1,"session_id":"foreign-session","run_id":None,"payload":{"method":"initialize","connection_id":"connection"}}
print(json.dumps(frame),flush=True)
line=sys.stdin.readline()
if line: open("unexpected-run","w").write(line)
'''
    opts = options(tmp_path, fake_server(tmp_path, body), session={"mode": "resume", "id": "chosen-session"})
    run_lua(nvim, tmp_path, f'''
assert(pilot.run(vim.json.decode({json.dumps(opts)})))
assert(vim.wait(8000, function() return pilot.status().settled end, 10))
assert(pilot.status().status == "incomplete")
''')
    assert not (tmp_path / "unexpected-run").exists()


def test_permission_evidence_inspection_is_readonly_then_explicit_decision(nvim, tmp_path):
    opts = options(tmp_path, decision_server(tmp_path))
    run_lua(nvim, tmp_path, f'''
vim.cmd.edit("selected.py")
local callback
vim.ui.select = function(_, _, reply) callback=reply end
assert(pilot.run(vim.json.decode({json.dumps(opts)})))
assert(vim.wait(8000, function() return callback ~= nil end, 10))
callback("Inspect evidence")
assert(not vim.bo.modifiable and vim.bo.buftype == "nofile")
assert(vim.fn.join(vim.api.nvim_buf_get_lines(0,0,-1,false),"\\n"):find("permission",1,true))
assert(not pilot.status().settled)
pilot.decision()
callback("Deny")
assert(vim.wait(8000, function() return pilot.status().settled end, 10))
assert(pilot.status().status == "completed")
''')
    assert json.loads((tmp_path / "reply.json").read_text())["params"]["approved"] is False


def test_cancel_retires_delayed_new_task_prompt_before_any_launch(nvim, tmp_path):
    opts = options(tmp_path, ["must-not-launch"])
    run_lua(nvim, tmp_path, f'''
local opts=vim.json.decode({json.dumps(opts)})
pilot.setup({{command=opts.command,project=opts.project,paths=opts.paths}})
local answer
vim.ui.input=function(_, callback) answer=callback end
vim.cmd.HenchmanNew()
assert(answer and pilot.status() == nil)
pilot.cancel()
answer("late task must not execute")
assert(pilot.status() == nil)
''')


@pytest.mark.parametrize("fault", ["sequence", "partial", "oversize", "exit"])
def test_bad_transport_never_claims_completed_and_restores_buffers(nvim, tmp_path, fault):
    body = '''
first=json.loads(sys.stdin.readline())
frame={"v":1,"seq":1,"kind":"response","request_id":1,"session_id":"session","run_id":None,"payload":{"method":"initialize","connection_id":"connection"}}
print(json.dumps(frame),flush=True)
run=json.loads(sys.stdin.readline())
'''
    if fault == "sequence":
        body += 'frame.update(seq=3,kind="result",request_id=2,payload={"status":"completed","task_verified":False});print(json.dumps(frame),flush=True)\n'
    elif fault == "partial":
        body += 'sys.stdout.write("{\\\"partial\\\":");sys.stdout.flush()\n'
    elif fault == "oversize":
        body += 'sys.stdout.write("x"*1100000);sys.stdout.flush()\n'
    else:
        body += 'sys.exit(7)\n'
    opts = options(tmp_path, fake_server(tmp_path, body))
    run_lua(nvim, tmp_path, f'''
vim.cmd.edit("selected.py")
vim.bo.autoread = true
local opts = vim.json.decode({json.dumps(opts)})
assert(pilot.run(opts))
assert(not vim.bo.modifiable and not vim.bo.autoread)
assert(vim.wait(8000, function() return pilot.status().settled end, 10))
assert(pilot.status().status == "incomplete")
assert(vim.bo.modifiable and vim.bo.autoread)
assert(not vim.bo.modified)
''')


def test_partial_unicode_frames_and_terminal_exit_agree(nvim, tmp_path):
    body = '''
json.loads(sys.stdin.readline())
frames=[{"v":1,"seq":1,"kind":"response","request_id":1,"session_id":"session","run_id":None,"payload":{"method":"initialize","connection_id":"connection"}},
{"v":1,"seq":2,"kind":"event","request_id":2,"session_id":"session","run_id":"actual-run","payload":{"type":"run_started"}},
{"v":1,"seq":3,"kind":"event","request_id":2,"session_id":"session","run_id":"actual-run","payload":{"type":"content","data":"é🙂"}},
{"v":1,"seq":4,"kind":"result","request_id":2,"session_id":"session","run_id":"actual-run","payload":{"status":"completed","runtime_status":"completed","task_verified":False,"error":None}}]
for i,frame in enumerate(frames):
    raw=(json.dumps(frame,ensure_ascii=False)+"\\n").encode()
    for offset in range(0,len(raw),3):
        sys.stdout.buffer.write(raw[offset:offset+3]);sys.stdout.buffer.flush()
    if i==0: json.loads(sys.stdin.readline())
'''
    opts = options(tmp_path, fake_server(tmp_path, body))
    run_lua(nvim, tmp_path, f'''
vim.cmd.edit("selected.py")
local opts = vim.json.decode({json.dumps(opts)})
assert(pilot.run(opts))
assert(vim.wait(8000, function() return pilot.status().settled end, 10))
local state = pilot.status()
assert(state.status == "completed" and state.run_id == "actual-run")
assert(state.task_verified == false and state.exit_code == 0)
assert(state.output:find("é🙂", 1, true))
assert(vim.bo.modifiable)
''')


def decision_server(tmp_path, *, review_body=""):
    return fake_server(tmp_path, '''
if "checkpoint" in sys.argv:
''' + ("    " + review_body.replace("\n", "\n    ") if review_body else '    print(json.dumps({"checkpoints":[],"checkpoints_omitted":0,"task_verified":False}))') + '''
    sys.exit(0)
json.loads(sys.stdin.readline())
base={"v":1,"seq":1,"kind":"response","request_id":1,"session_id":"session","run_id":None,"payload":{"method":"initialize","connection_id":"connection"}}
print(json.dumps(base),flush=True)
run=json.loads(sys.stdin.readline())
base.update(seq=2,kind="event",request_id=2,run_id="actual-run",payload={"type":"permission","state":"pending","decision_id":"decision","generation":1,"tool_name":"edit_file"})
print(json.dumps(base),flush=True)
reply=json.loads(sys.stdin.readline())
open("reply.json","w").write(json.dumps(reply))
status="cancelled" if reply["method"]=="cancel" else "completed"
base.update(seq=3,kind="response",request_id=reply["id"],payload={"method":reply["method"],"state":"requested" if reply["method"]=="cancel" else "received"})
print(json.dumps(base),flush=True)
base.update(seq=4,kind="result",request_id=2,payload={"status":status,"runtime_status":"completed" if status=="completed" else None,"task_verified":False,"error":None})
print(json.dumps(base),flush=True)
sys.exit(130 if status=="cancelled" else 0)
''')


def test_forced_edit_cancels_and_stale_permission_cannot_authorize(nvim, tmp_path):
    opts = options(tmp_path, decision_server(tmp_path))
    run_lua(nvim, tmp_path, f'''
vim.cmd.edit("selected.py")
local selected = vim.api.nvim_get_current_buf()
local callback
vim.ui.select = function(_, _, reply) callback = reply end
local opts = vim.json.decode({json.dumps(opts)})
assert(pilot.run(opts))
assert(vim.wait(8000, function() return callback ~= nil end, 10))
vim.bo[selected].modifiable = true
vim.api.nvim_buf_set_lines(selected, 0, -1, false, {{"forced unsaved edit"}})
assert(vim.wait(8000, function() return pilot.status().settled end, 10))
callback("Allow once")
assert(pilot.status().status == "cancelled" and pilot.status().buffer_conflict)
assert(vim.bo[selected].modified and vim.bo[selected].modifiable)
assert(vim.api.nvim_buf_get_lines(selected,0,-1,false)[1] == "forced unsaved edit")
''')
    reply = json.loads((tmp_path / "reply.json").read_text())
    assert reply["method"] == "cancel" and reply["params"]["run_id"] == "actual-run"
    assert (tmp_path / "selected.py").read_text() == "value = 1\n"


def test_unsaved_alias_buffer_refuses_physical_selection(nvim, tmp_path):
    opts = options(tmp_path, ["must-not-launch"])
    (tmp_path / "alias.py").symlink_to(tmp_path / "selected.py")
    run_lua(nvim, tmp_path, f'''
vim.cmd.edit("alias.py")
vim.api.nvim_buf_set_lines(0,0,-1,false,{{"unsaved alias"}})
local ok, reason = pilot.run(vim.json.decode({json.dumps(opts)}))
assert(not ok and reason:find("Unsaved",1,true))
assert(vim.bo.modified and vim.bo.modifiable)
''')


@pytest.mark.parametrize("review_body", ["time.sleep(60)", "sys.stdout.write('x'*600000);sys.stdout.flush()"])
def test_review_child_timeout_or_output_limit_is_joined_and_unavailable(nvim, tmp_path, review_body):
    opts = options(tmp_path, decision_server(tmp_path, review_body=review_body))
    run_lua(nvim, tmp_path, f'''
pilot.setup({{review_ms=50}})
vim.ui.select = function(_, _, reply) reply("Deny") end
assert(pilot.run(vim.json.decode({json.dumps(opts)})))
assert(vim.wait(8000, function() return pilot.status().settled end, 10))
local finished = false
assert(pilot.review(function(value, reason)
  assert(value == nil and reason:find("unavailable",1,true)); finished=true
end))
assert(vim.wait(8000, function() return finished end, 10))
assert(pilot.status().runtime_result.status == "completed")
''')
    assert json.loads((tmp_path / "reply.json").read_text())["params"]["approved"] is False


def test_editor_shutdown_joins_owned_review_before_returning(nvim, tmp_path):
    opts = options(tmp_path, decision_server(tmp_path, review_body='open("review-started","w").close();time.sleep(60)'))
    run_lua(nvim, tmp_path, f'''
vim.ui.select=function(_,_,reply) reply("Deny") end
assert(pilot.run(vim.json.decode({json.dumps(opts)})))
assert(vim.wait(8000,function() return pilot.status().settled end,10))
local joined=false
assert(pilot.review(function(value) assert(value == nil); joined=true end))
assert(vim.wait(8000,function() return vim.uv.fs_stat("review-started") ~= nil end,10))
pilot.shutdown()
assert(joined,"review cleanup was not joined")
''')


def test_cancel_before_admission_uses_owned_request_with_null_run_id(nvim, tmp_path):
    body = '''
json.loads(sys.stdin.readline())
base={"v":1,"seq":1,"kind":"response","request_id":1,"session_id":"session","run_id":None,"payload":{"method":"initialize","connection_id":"connection"}}
print(json.dumps(base),flush=True)
json.loads(sys.stdin.readline());open("started","w").close()
reply=json.loads(sys.stdin.readline());open("reply.json","w").write(json.dumps(reply))
base.update(seq=2,kind="result",request_id=2,run_id="actual-run",payload={"status":"cancelled","runtime_status":None,"task_verified":False,"error":None})
print(json.dumps(base),flush=True);sys.exit(130)
'''
    opts = options(tmp_path, fake_server(tmp_path, body))
    run_lua(nvim, tmp_path, f'''
assert(pilot.run(vim.json.decode({json.dumps(opts)})))
assert(vim.wait(8000, function() return vim.uv.fs_stat("started") ~= nil end, 10))
pilot.cancel()
assert(vim.wait(8000, function() return pilot.status().settled end, 10))
assert(pilot.status().status == "cancelled")
''')
    reply = json.loads((tmp_path / "reply.json").read_text())
    assert reply["params"] == {"run_request_id": 2, "run_id": None}


@contextmanager
def scripted_provider(tmp_path, *, stalled=False):
    """An owned local SSE server implements a fixed script, never inference."""
    requests = []
    release = threading.Event()
    actions = [
        ("read_file", {"path": "calculator.py"}),
        ("edit_file", {"path": "calculator.py", "old_str": "return a - b", "new_str": "return a + b"}),
        ("pytest_run", {"path": "test_calculator.py", "timeout": 20}),
    ]
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_args):
            pass

        def do_POST(self):
            assert self.path == "/v1/chat/completions"
            size = int(self.headers["Content-Length"])
            assert 0 < size < 4 * 1024 * 1024
            request = json.loads(self.rfile.read(size))
            assert request["model"] == "scripted-pilot" and request["stream"] is True
            index = len(requests)
            requests.append(request)
            (tmp_path / "provider-entered").touch()
            if stalled:
                release.wait(40)
            delta = {"content": "The check result is recorded; review the changes."}
            reason = "stop"
            if index < len(actions):
                name, arguments = actions[index]
                delta = {"tool_calls": [{"index": 0, "id": f"call-{index}", "type": "function",
                                         "function": {"name": name, "arguments": json.dumps(arguments)}}]}
                reason = "tool_calls"
            chunk = {"id": "scripted", "object": "chat.completion.chunk", "created": 1, "model": "scripted-pilot",
                     "choices": [{"index": 0, "delta": delta, "finish_reason": reason}],
                     "usage": {"prompt_tokens": 20, "completion_tokens": 10, "total_tokens": 30}}
            body = ("data: " + json.dumps(chunk) + "\n\ndata: [DONE]\n\n").encode()
            try:
                self.send_response(200)
                self.send_header("Content-Type", "text/event-stream")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            except (BrokenPipeError, ConnectionResetError):
                pass
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}/v1", requests
    finally:
        release.set()
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
        assert not thread.is_alive()


def prepare_project(tmp_path, url):
    (tmp_path / "calculator.py").write_text("def add(a, b):\n    return a - b\n")
    (tmp_path / "test_calculator.py").write_text("from calculator import add\n\ndef test_add():\n    assert add(3, 2) == 5\n")
    (tmp_path / "unrelated.py").write_text("dirty=  7\n")
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True, timeout=10)
    subprocess.run(["git", "add", "calculator.py", "test_calculator.py", "unrelated.py"], cwd=tmp_path, check=True, timeout=10)
    config = tmp_path / ".henchman"
    config.mkdir()
    (config / "settings.yaml").write_text(
        "providers:\n  default: openai_compat\n  openai_compat:\n    model: scripted-pilot\n"
        f"    base_url: {url}\n    api_key: fixture-only\n"
    )
    return (tmp_path / ".git/index").read_bytes()


@pytest.mark.parametrize("approved", [True, False])
def test_actual_editor_inspect_edit_check_and_correlated_review(nvim, tmp_path, approved):
    with scripted_provider(tmp_path) as (url, requests):
        index = prepare_project(tmp_path, url)
        opts = json.dumps({"project": str(tmp_path), "paths": ["calculator.py", "test_calculator.py"],
                           "command": [sys.executable, "-m", "henchman"], "session": {"mode": "new"},
                           "prompt": "Inspect the calculator, fix addition, run its test, and report the evidence."})
        run_lua(nvim, tmp_path, f'''
vim.cmd.edit("unrelated.py")
local dirty = vim.api.nvim_get_current_buf()
vim.api.nvim_buf_set_lines(dirty,0,-1,false,{{"unsaved unrelated draft"}})
vim.cmd("split calculator.py")
local selected = vim.api.nvim_get_current_buf()
vim.ui.select = function(_, opts, reply)
  if opts.prompt:find("pytest_run",1,true) then reply("Allow once")
  else reply({json.dumps('Allow once' if approved else 'Deny')}) end
end
assert(pilot.run(vim.json.decode({json.dumps(opts)})))
assert(vim.wait(30000, function() return pilot.status().settled end, 10), "run did not settle")
local state = pilot.status()
assert(state.status == "completed", vim.json.encode(state))
assert(state.run_id and state.session_id and state.task_verified == false)
assert(vim.bo[selected].modifiable and vim.bo[dirty].modified)
assert(vim.api.nvim_buf_get_lines(dirty,0,-1,false)[1] == "unsaved unrelated draft")
local reviewed, payload = false, nil
assert(pilot.review(function(value, reason) assert(value, reason); payload=value; reviewed=true end))
assert(vim.wait(15000, function() return reviewed end, 10), "review did not settle")
assert(payload.task_verified == false)
vim.fn.writefile({{vim.json.encode({{state=state,review=payload}})}}, "editor-receipt.json")
''', timeout=55)
    receipt = json.loads((tmp_path / "editor-receipt.json").read_text())
    source = (tmp_path / "calculator.py").read_text()
    assert ("return a + b" in source) is approved
    assert (tmp_path / ".git/index").read_bytes() == index
    assert (tmp_path / "unrelated.py").read_text() == "dirty=  7\n"
    assert len(requests) == 4
    returned_tools = [message for request in requests for message in request["messages"] if message["role"] == "tool"]
    assert any(("Test execution passed" if approved else "Test execution failed") in str(message["content"]) for message in returned_tools)
    captures = receipt["review"]["checkpoints"]
    assert bool(captures) is approved
    if approved:
        assert all(record["operation"]["run_id"] == receipt["state"]["run_id"] for record in captures)
        assert any("return a + b" in hunk["after"] for record in captures for file in record["files"] for hunk in file["hunks"])
        oracle = subprocess.run([sys.executable, "-m", "pytest", "-q", "test_calculator.py"], cwd=tmp_path,
                                capture_output=True, text=True, timeout=20, check=False)
        assert oracle.returncode == 0 and "1 passed" in oracle.stdout


def test_actual_editor_cancel_joins_real_runtime_without_edits(nvim, tmp_path):
    with scripted_provider(tmp_path, stalled=True) as (url, requests):
        index = prepare_project(tmp_path, url)
        opts = json.dumps({"project": str(tmp_path), "paths": ["calculator.py"], "command": [sys.executable, "-m", "henchman"],
                           "session": {"mode": "new"}, "prompt": "Inspect the calculator."})
        run_lua(nvim, tmp_path, f'''
vim.cmd.edit("calculator.py")
assert(pilot.run(vim.json.decode({json.dumps(opts)})))
assert(vim.wait(15000, function() return vim.uv.fs_stat("provider-entered") ~= nil end, 10))
pilot.cancel()
assert(vim.wait(10000, function() return pilot.status().settled end, 10))
local state = pilot.status()
assert(state.status == "cancelled" and state.exit_code == 130, vim.json.encode(state))
assert(state.runtime_result.status == "cancelled" and state.task_verified == false)
assert(vim.bo.modifiable)
''', timeout=35)
    assert len(requests) == 1
    assert (tmp_path / "calculator.py").read_text() == "def add(a, b):\n    return a - b\n"
    assert (tmp_path / ".git/index").read_bytes() == index


_MALFORMED_FRAMES = [
    "event_null",
    "event_missing",
    "result_null",
    "result_missing",
    "unissued_response",
    "wrong_method_response",
    "duplicate_run",
    "duplicate_status",
    "runtime_mismatch",
    "rejected_with_run",
    "escaped_duplicate",
    "nested_duplicate",
    "nan",
    "infinity",
    "negative_infinity",
    "overflow",
    "leading_zero",
    "trailing_decimal",
    "missing_runtime",
    "missing_error",
    "unexpected_result_field",
    "completed_error",
    "invalid_utf8",
    "overlong_utf8",
    "surrogate_utf8",
    "above_unicode_utf8",
]


@pytest.mark.parametrize("case", _MALFORMED_FRAMES)
def test_malformed_server_correlation_cannot_complete(nvim, tmp_path, case):
    body = """
json.loads(sys.stdin.readline())
base={"v":1,"seq":1,"kind":"response","request_id":1,"session_id":"session","run_id":None,"payload":{"method":"initialize","connection_id":"connection"}}
print(json.dumps(base),flush=True)
json.loads(sys.stdin.readline())
base.update(seq=2,kind="event",request_id=2,run_id="actual-run",payload={"type":"run_started"})
print(json.dumps(base),flush=True)
"""
    terminal = {
        "v": 1,
        "seq": 3,
        "kind": "result",
        "request_id": 2,
        "session_id": "session",
        "run_id": "actual-run",
        "payload": {
            "status": "completed",
            "runtime_status": "completed",
            "task_verified": False,
            "error": None,
        },
    }
    code = 0
    if case.startswith("event_"):
        middle = {
            **terminal,
            "kind": "event",
            "payload": {"type": "content", "data": "unbound event"},
        }
        if case == "event_null":
            middle["run_id"] = None
        else:
            middle.pop("run_id")
        body += "print(" + repr(json.dumps(middle)) + ",flush=True)\n"
        terminal["seq"] = 4
    elif case.startswith("result_"):
        if case == "result_null":
            terminal["run_id"] = None
        else:
            terminal.pop("run_id")
    elif case in {"unissued_response", "wrong_method_response"}:
        middle = {
            **terminal,
            "kind": "response",
            "request_id": 999 if case == "unissued_response" else 2,
            "payload": {"method": "permission.respond", "state": "received"},
        }
        body += "print(" + repr(json.dumps(middle)) + ",flush=True)\n"
        terminal["seq"] = 4
    elif case == "runtime_mismatch":
        terminal["payload"]["runtime_status"] = "failed"
    elif case == "rejected_with_run":
        terminal["payload"].update(status="rejected", runtime_status=None)
        code = 1
    if case == "missing_runtime":
        terminal["payload"].pop("runtime_status")
    elif case == "missing_error":
        terminal["payload"].pop("error")
    elif case == "unexpected_result_field":
        terminal["payload"]["accepted"] = True
    elif case == "completed_error":
        terminal["payload"]["error"] = {"code": "failure", "message": "failed"}
    raw = json.dumps(terminal)
    if case == "escaped_duplicate":
        raw = raw.replace(
            '"status": "completed"', '"sta\\u0074us": "failed", "status": "completed"'
        )
    if case == "nested_duplicate":
        raw = raw[:-2] + ',"budget":{"used":1,"used":2}}}'
    for variant, token in {
        "nan": "NaN",
        "infinity": "Infinity",
        "negative_infinity": "-Infinity",
        "overflow": "1e999",
        "leading_zero": "01",
        "trailing_decimal": "1.",
    }.items():
        if case == variant:
            raw = raw[:-2] + ',"budget":{"used":' + token + "}}}"
    if case == "duplicate_run":
        raw = raw.replace('"run_id": "actual-run"', '"run_id": "foreign", "run_id": "actual-run"')
    if case == "duplicate_status":
        raw = raw.replace('"status": "completed"', '"status": "failed", "status": "completed"')
    invalid_utf8 = {
        "invalid_utf8": b"\xff", "overlong_utf8": b"\xc0\xaf",
        "surrogate_utf8": b"\xed\xa0\x80", "above_unicode_utf8": b"\xf4\x90\x80\x80",
    }
    if case in invalid_utf8:
        data = raw[:-2].encode() + b',"budget":{"text":"' + invalid_utf8[case] + b'"}}}\n'
        body += f"sys.stdout.buffer.write({data!r});sys.stdout.flush()\n"
    else:
        body += "print(" + repr(raw) + ",flush=True)\n"
    body += "sys.exit(" + str(code) + ")\n"
    opts = options(tmp_path, fake_server(tmp_path, body))
    run_lua(
        nvim,
        tmp_path,
        f"""
assert(pilot.run(vim.json.decode({json.dumps(opts)})))
assert(vim.wait(8000,function() return pilot.status().settled end,10))
local state=pilot.status()
vim.fn.writefile({{vim.json.encode(state)}},"peer-state.json")
assert(state.status=="incomplete","Malformed server frame was accepted")
vim.fn.writefile({{"complete"}},"peer-finished")
""",
    )
    assert (tmp_path / "peer-finished").exists()


@pytest.mark.parametrize(
    ("status", "runtime_status", "admitted"),
    [
        ("completed", "completed", True),
        ("completed", "responded", True),
        ("failed", "failed", True),
        ("cancelled", None, True),
        ("incomplete", "completed", True),
        ("cancelled", None, False),
        ("incomplete", None, False),
        ("rejected", None, False),
    ],
)
def test_valid_shared_encoder_terminal_outcomes_remain_distinct(
    nvim, tmp_path, status, runtime_status, admitted
):
    from henchman.cli.headless_protocol import ServerEncoder

    encoder = ServerEncoder()
    initialize = encoder.encode(
        kind="response",
        request_id=1,
        session_id="session",
        run_id=None,
        payload={"method": "initialize", "connection_id": "connection"},
    )
    result = encoder.encode(
        kind="result",
        request_id=2,
        session_id="session",
        run_id="actual-run" if admitted else None,
        payload={
            "status": status,
            "runtime_status": runtime_status,
            "task_verified": False,
            "error": None,
        },
    )
    exit_code = 0 if status == "completed" else 130 if status == "cancelled" else 1
    body = (
        "json.loads(sys.stdin.readline())\n"
        + f"sys.stdout.buffer.write({initialize!r});sys.stdout.flush()\n"
        + "json.loads(sys.stdin.readline())\n"
        + f"sys.stdout.buffer.write({result!r});sys.stdout.flush()\nsys.exit({exit_code})\n"
    )
    opts = options(tmp_path, fake_server(tmp_path, body))
    run_lua(
        nvim,
        tmp_path,
        f"""
assert(pilot.run(vim.json.decode({json.dumps(opts)})))
assert(vim.wait(8000,function() return pilot.status().settled end,10))
local state=pilot.status()
assert(state.status=={json.dumps(status)},vim.json.encode(state))
assert(state.runtime_result.status=={json.dumps(status)} and state.task_verified==false)
""",
    )


def test_acknowledged_decisions_release_bounded_request_bookkeeping(nvim, tmp_path):
    body = """
json.loads(sys.stdin.readline())
frame={"v":1,"seq":1,"kind":"response","request_id":1,"session_id":"session","run_id":None,"payload":{"method":"initialize","connection_id":"connection"}}
print(json.dumps(frame),flush=True)
json.loads(sys.stdin.readline())
for index in range(40):
    frame.update(seq=index*2+2,kind="event",request_id=2,run_id="actual-run",payload={"type":"permission","state":"pending","decision_id":"decision-"+str(index),"generation":index+1,"tool_name":"edit_file"})
    print(json.dumps(frame),flush=True)
    reply=json.loads(sys.stdin.readline())
    assert reply["method"]=="permission.respond" and reply["params"]["approved"] is False
    frame.update(seq=index*2+3,kind="response",request_id=reply["id"],payload={"method":"permission.respond","state":"received"})
    print(json.dumps(frame),flush=True)
frame.update(seq=82,kind="result",request_id=2,payload={"status":"completed","runtime_status":"completed","task_verified":False,"error":None})
print(json.dumps(frame),flush=True)
"""
    opts = options(tmp_path, fake_server(tmp_path, body))
    run_lua(
        nvim,
        tmp_path,
        f"""
vim.ui.select=function(_,_,reply) reply("Deny") end
assert(pilot.run(vim.json.decode({json.dumps(opts)})))
assert(vim.wait(8000,function() return pilot.status().settled end,10))
assert(pilot.status().status=="completed",vim.json.encode(pilot.status()))
""",
    )
