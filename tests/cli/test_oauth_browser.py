"""Browser launch uses owned synthetic children; no browser or account is opened."""

import asyncio
import hashlib
import io
import json
import os
import sys
import time
import traceback
from pathlib import Path

import pytest

from henchman.cli import oauth_browser, oauth_browser_child

URL = "https://issuer.invalid/authorize?state=browser-private-canary&code_challenge=challenge"


@pytest.fixture
def synthetic_launcher(tmp_path, monkeypatch):
    script = tmp_path / "launcher.py"
    script.write_text('''import hashlib,json,os,pathlib,sys,time
mode, target = sys.argv[1:]
if mode == "windows_text_stream": sys.stdout.reconfigure(newline="\\r\\n")
pathlib.Path(target + ".started").touch()
if mode == "ignore_term":
    import signal
    signal.signal(signal.SIGTERM, signal.SIG_IGN)
if mode == "no_ready": time.sleep(30)
if mode == "bad_ready":
    print("private-ready-canary", flush=True)
    time.sleep(30)
if mode == "oversized_ready":
    print("x" * 4096, flush=True)
    time.sleep(30)
if mode == "crlf_ready":
    sys.stdout.buffer.write(b"READY\\r\\n")
    sys.stdout.buffer.flush()
    time.sleep(30)
if mode == "wait_ready":
    while not pathlib.Path(target + ".ready").exists(): time.sleep(.005)
# Match the real helper's binary control protocol on every platform.
sys.stdout.buffer.write(b"READY\\n")
sys.stdout.buffer.flush()
value = sys.stdin.buffer.readline(9000)
if value:
    pathlib.Path(target).write_text(json.dumps({"sha256":hashlib.sha256(value).hexdigest(),
        "env":dict(os.environ)}))
if mode == "delayed_success": time.sleep(.65)
if mode in {"hold", "ignore_term"}: time.sleep(30)
if mode == "wait_exit":
    while not pathlib.Path(target + ".exit").exists(): time.sleep(.005)
if mode == "failure":
    print("private-launch-failure-canary", flush=True)
    sys.exit(1)
if mode == "flood":
    sys.stdout.write("private-output-canary" * 100000)
    sys.stdout.flush()
    time.sleep(30)
''')
    calls, processes = [], []
    original = asyncio.create_subprocess_exec

    async def spawn(*args, **kwargs):
        calls.append((args, kwargs))
        process = await original(*args, **kwargs)
        processes.append(process)
        return process

    monkeypatch.setattr(oauth_browser.asyncio, "create_subprocess_exec", spawn)
    monkeypatch.setattr(oauth_browser, "READY_TIMEOUT_SECONDS", 2)
    monkeypatch.setattr(oauth_browser, "LAUNCH_TIMEOUT_SECONDS", .3)
    monkeypatch.setattr(oauth_browser, "STOP_TIMEOUT_SECONDS", .2)

    def choose(mode):
        target = tmp_path / (mode + ".json")
        monkeypatch.setattr(oauth_browser, "_child_command", lambda: (sys.executable, "-I", str(script), mode, str(target)))
        return target

    return choose, calls, processes


async def wait_until(predicate, *, operation=None, timeout=2):
    async with asyncio.timeout(timeout):
        while not predicate():
            if operation is not None and operation.done():
                await operation
                raise AssertionError("Operation completed before the expected event")
            await asyncio.sleep(.001)


async def test_wait_until_can_allow_slow_owned_startup_without_hiding_early_failure():
    ready = asyncio.Event()

    async def delayed_start():
        await asyncio.sleep(2.1)
        ready.set()

    startup = asyncio.create_task(delayed_start())
    try:
        await wait_until(ready.is_set, operation=startup, timeout=4)
        await startup
    finally:
        if not startup.done():
            startup.cancel()
        await asyncio.gather(startup, return_exceptions=True)

    async def fail_early():
        raise RuntimeError("launcher setup failed")

    failed = asyncio.create_task(fail_early())
    with pytest.raises(RuntimeError, match="launcher setup failed"):
        await wait_until(lambda: False, operation=failed, timeout=4)

    async def complete_early():
        return None

    completed = asyncio.create_task(complete_early())
    with pytest.raises(AssertionError, match="completed before the expected event"):
        await wait_until(lambda: False, operation=completed, timeout=4)


def assert_joined(processes):
    assert processes and all(process.returncode is not None for process in processes)
    assert not [task for task in asyncio.all_tasks() if task.get_name().startswith("henchman-oauth-browser")]


@pytest.mark.parametrize("mode", ["success", "windows_text_stream", "delayed_success"])
async def test_native_child_receives_url_only_on_stdin_after_ready_and_is_reaped(synthetic_launcher, monkeypatch, mode):
    choose, calls, processes = synthetic_launcher
    target = choose(mode)
    # A successful child may exit slowly on a loaded native runner. The short
    # fixture deadline remains in place for the timeout and cleanup tests.
    monkeypatch.setattr(oauth_browser, "LAUNCH_TIMEOUT_SECONDS", 3)
    monkeypatch.setenv("OPENAI_API_KEY", "provider-private-canary")
    monkeypatch.setenv("HMN_MCP_AUTH_TOKEN", "mcp-private-canary")
    monkeypatch.setenv("BROWSER", "unsafe-shell-template %s")
    monkeypatch.setenv("PYTHONPATH", "untrusted-module-path")
    monkeypatch.setenv("DBUS_SESSION_BUS_ADDRESS", "unix:path=/owned/desktop-bus")
    guards = []
    await oauth_browser.open_oauth_browser(URL, authorize=lambda: guards.append(True))
    data = json.loads(target.read_text())
    assert data["sha256"] == hashlib.sha256((URL + "\n").encode()).hexdigest()
    assert len(guards) >= 3
    assert len(calls) == 1 and all(URL not in str(value) for value in calls[0][0])
    assert calls[0][0][1] == "-I" and calls[0][1]["stderr"] == asyncio.subprocess.DEVNULL
    assert not {"OPENAI_API_KEY", "HMN_MCP_AUTH_TOKEN", "BROWSER", "PYTHONPATH"} & data["env"].keys()
    assert data["env"]["DBUS_SESSION_BUS_ADDRESS"] == "unix:path=/owned/desktop-bus"
    assert_joined(processes)


@pytest.mark.parametrize("url", ["http://issuer.invalid/a", "file:///private", "https://user:secret@issuer.invalid/a",
                                  "https://issuer.invalid/a#private", "https://issuer.invalid/a\nprivate", "https://issuer.invalid/" + "x" * 8192])
async def test_invalid_url_is_rejected_before_spawn_without_echo(synthetic_launcher, url):
    _choose, calls, _processes = synthetic_launcher
    with pytest.raises(oauth_browser.BrowserLaunchError) as caught:
        await oauth_browser.open_oauth_browser(url, authorize=lambda: None)
    assert calls == [] and url not in str(caught.value)


@pytest.mark.parametrize("authorize", [None, lambda: False])
async def test_explicit_current_authority_is_required_before_spawn(synthetic_launcher, authorize):
    _choose, calls, _processes = synthetic_launcher
    with pytest.raises(oauth_browser.BrowserLaunchError):
        await oauth_browser.open_oauth_browser(URL, authorize=authorize)
    assert calls == []


async def test_authority_revoked_while_waiting_ready_never_hands_off_url(synthetic_launcher):
    choose, _calls, processes = synthetic_launcher
    target = choose("wait_ready")
    current = [True]

    def authorize():
        if not current[0]:
            raise RuntimeError("private-authority-canary")

    operation = asyncio.create_task(oauth_browser.open_oauth_browser(URL, authorize=authorize))
    await wait_until(lambda: bool(processes))
    current[0] = False
    Path(str(target) + ".ready").touch()
    with pytest.raises(oauth_browser.BrowserLaunchError) as caught:
        await asyncio.wait_for(operation, 2)
    assert "canary" not in "".join(traceback.format_exception(caught.value))
    assert not target.exists()
    assert_joined(processes)


@pytest.mark.parametrize("mode", ["no_ready", "bad_ready", "oversized_ready", "crlf_ready", "hold", "failure", "flood"])
async def test_failure_timeout_and_output_bounds_settle_owned_child(synthetic_launcher, mode):
    choose, calls, processes = synthetic_launcher
    target = choose(mode)
    with pytest.raises(oauth_browser.BrowserLaunchError) as caught:
        await asyncio.wait_for(oauth_browser.open_oauth_browser(URL, authorize=lambda: None), 3)
    details = "".join(traceback.format_exception(caught.value))
    assert "canary" not in details and len(calls) == 1
    assert ("may have opened" in details) == target.exists()
    assert Path(str(target) + ".started").exists()
    assert_joined(processes)


@pytest.mark.parametrize("phase", ["ready", "handoff"])
async def test_cancel_preserves_reason_and_reports_possible_handoff(synthetic_launcher, phase):
    choose, _calls, processes = synthetic_launcher
    target = choose("no_ready" if phase == "ready" else "hold")
    operation = asyncio.create_task(oauth_browser.open_oauth_browser(URL, authorize=lambda: None))
    await wait_until(lambda: bool(processes) and (phase == "ready" or target.exists()))
    operation.cancel("owned browser cancellation")
    with pytest.raises(asyncio.CancelledError, match="owned browser cancellation") as caught:
        await asyncio.wait_for(operation, 2)
    assert ("may have opened" in "".join(getattr(caught.value, "__notes__", []))) == (phase == "handoff")
    assert_joined(processes)


async def test_cancel_during_spawn_joins_late_owned_process_and_repeated_cancellation(synthetic_launcher, monkeypatch):
    choose, _calls, processes = synthetic_launcher
    target = choose("hold")
    spawned, release = asyncio.Event(), asyncio.Event()
    original = oauth_browser.asyncio.create_subprocess_exec

    async def delayed(*args, **kwargs):
        process = await original(*args, **kwargs)
        spawned.set()
        await release.wait()
        return process

    monkeypatch.setattr(oauth_browser.asyncio, "create_subprocess_exec", delayed)
    operation = asyncio.create_task(oauth_browser.open_oauth_browser(URL, authorize=lambda: None))
    await asyncio.wait_for(spawned.wait(), 2)
    operation.cancel("spawn cancellation")
    await asyncio.sleep(.01)
    operation.cancel("repeated cancellation")
    release.set()
    with pytest.raises(asyncio.CancelledError, match="spawn cancellation"):
        await asyncio.wait_for(operation, 2)
    assert not target.exists()
    assert_joined(processes)


def test_environment_preserves_desktop_os_values_and_excludes_loader_credentials():
    source = {"HOME": "/owned/home", "SystemRoot": "C:\\Windows", "DISPLAY": ":1",
              "WAYLAND_DISPLAY": "wayland-1", "XAUTHORITY": "/owned/xauth",
              "XDG_ACTIVATION_TOKEN": "owned-activation", "DESKTOP_STARTUP_ID": "owned-startup",
              "BROWSER": "shell %s", "LD_PRELOAD": "private-loader", "SSH_AUTH_SOCK": "private-agent",
              "HTTPS_PROXY": "https://private:secret@proxy", "PATH": os.pathsep.join([".", "", os.defpath])}
    result = oauth_browser_child.browser_environment(source)
    for name in ("HOME", "SystemRoot", "DISPLAY", "WAYLAND_DISPLAY", "XAUTHORITY", "XDG_ACTIVATION_TOKEN", "DESKTOP_STARTUP_ID"):
        assert result[name] == source[name]
    assert not {"BROWSER", "LD_PRELOAD", "SSH_AUTH_SOCK", "HTTPS_PROXY"} & result.keys()
    assert all(os.path.isabs(part) for part in result["PATH"].split(os.pathsep))


@pytest.mark.parametrize("platform", ["linux", "darwin", "win32"])
def test_platform_adapters_use_argv_or_native_open_without_shell(monkeypatch, platform):
    called = []
    monkeypatch.setattr(oauth_browser_child.shutil, "which", lambda _name, **_kwargs: "/owned/bin/xdg-open")
    monkeypatch.setattr(oauth_browser_child.os.path, "isfile", lambda _path: True)
    monkeypatch.setattr(oauth_browser_child.os.path, "isabs", lambda _path: True)
    monkeypatch.setattr(oauth_browser_child.os, "access", lambda *_: True)
    monkeypatch.setattr(oauth_browser_child.os, "execve", lambda path, args, env: called.append((path, args, env)))
    monkeypatch.setattr(oauth_browser_child.os, "startfile", lambda url, operation: called.append((url, operation)), raising=False)
    environment = {"DISPLAY": ":1", "PATH": os.defpath}
    backend = oauth_browser_child.resolve_backend(platform, environment)
    oauth_browser_child.launch(backend, URL, environment)
    assert len(called) == 1
    if platform == "win32":
        assert called[0] == (URL, "open")
    else:
        expected = "/usr/bin/open" if platform == "darwin" else "/owned/bin/xdg-open"
        assert called[0] == (expected, [expected, URL], environment)


def test_child_protocol_uses_fixed_status_and_redirects_descriptors_before_launch(monkeypatch):
    events = []
    monkeypatch.setattr(oauth_browser_child, "resolve_backend", lambda *_: ("owned",))
    monkeypatch.setattr(oauth_browser_child, "redirect_protocol", lambda: events.append("redirect"))
    monkeypatch.setattr(oauth_browser_child, "launch", lambda backend, url, _environment: events.append((backend, url)))
    output = io.BytesIO()
    assert oauth_browser_child.run_protocol(io.BytesIO((URL + "\n").encode()), output, {}) == 0
    assert output.getvalue() == b"READY\n"
    assert events == ["redirect", (("owned",), URL)]
    output = io.BytesIO()
    assert oauth_browser_child.run_protocol(io.BytesIO((URL + "\nEXTRA\n").encode()), output, {}) != 0
    assert output.getvalue() == b"READY\nFAILED\n"


def test_unavailable_platform_never_accepts_a_url(monkeypatch):
    monkeypatch.setattr(oauth_browser_child, "resolve_backend", lambda *_: None)
    source, output = io.BytesIO((URL + "\n").encode()), io.BytesIO()
    assert oauth_browser_child.run_protocol(source, output, {}) != 0
    assert source.tell() == 0 and output.getvalue() == b"UNAVAILABLE\n"


async def test_spawn_failure_is_value_free_and_does_not_claim_uncertain_cleanup(synthetic_launcher, monkeypatch, tmp_path):
    _choose, calls, processes = synthetic_launcher
    monkeypatch.setattr(oauth_browser, "_child_command", lambda: (str(tmp_path / "missing-private-canary"),))
    with pytest.raises(oauth_browser.BrowserLaunchError) as caught:
        await oauth_browser.open_oauth_browser(URL, authorize=lambda: None)
    details = "".join(traceback.format_exception(caught.value))
    assert "canary" not in details and "cleanup could not confirm" not in details
    assert len(calls) == 1 and processes == []
    assert not [task for task in asyncio.all_tasks() if task.get_name().startswith("henchman-oauth-browser")]


async def test_spawn_exception_notes_are_not_copied_into_safe_diagnostic(monkeypatch):
    async def failed_spawn(*_args, **_kwargs):
        error = OSError("private-spawn-canary")
        error.add_note("private-exception-note-canary")
        raise error

    monkeypatch.setattr(oauth_browser.asyncio, "create_subprocess_exec", failed_spawn)
    with pytest.raises(oauth_browser.BrowserLaunchError) as caught:
        await oauth_browser.open_oauth_browser(URL, authorize=lambda: None)
    assert "canary" not in "".join(traceback.format_exception(caught.value))
    assert not [task for task in asyncio.all_tasks() if task.get_name().startswith("henchman-oauth-browser")]


async def test_terminate_failure_still_escalates_and_reaps_owned_child(synthetic_launcher, monkeypatch):
    choose, _calls, processes = synthetic_launcher
    target = choose("hold")
    operation = asyncio.create_task(oauth_browser.open_oauth_browser(URL, authorize=lambda: None))
    await wait_until(target.exists)

    def failed_terminate():
        raise OSError("private-terminate-canary")

    monkeypatch.setattr(processes[0], "terminate", failed_terminate)
    operation.cancel("cleanup cancellation")
    try:
        with pytest.raises(asyncio.CancelledError, match="cleanup cancellation") as caught:
            await asyncio.wait_for(operation, 2)
        assert "canary" not in "".join(traceback.format_exception(caught.value))
        assert_joined(processes)
    finally:
        # Red implementations must not leave the deliberately interrupted fixture.
        if processes[0].returncode is None:
            processes[0].kill()
            await processes[0].wait()


@pytest.mark.skipif(os.name == "nt", reason="Windows terminate already uses TerminateProcess")
async def test_uncooperative_launcher_is_killed_and_reaped(synthetic_launcher):
    import signal

    choose, _calls, processes = synthetic_launcher
    target = choose("ignore_term")
    operation = asyncio.create_task(oauth_browser.open_oauth_browser(URL, authorize=lambda: None))
    await wait_until(target.exists)
    operation.cancel("kill escalation")
    with pytest.raises(asyncio.CancelledError, match="kill escalation"):
        await asyncio.wait_for(operation, 2)
    assert processes[0].returncode == -signal.SIGKILL
    assert_joined(processes)


async def test_authority_change_after_handoff_does_not_report_current_success(synthetic_launcher):
    choose, _calls, processes = synthetic_launcher
    target = choose("wait_exit")
    active = [True]

    def authorize():
        if not active[0]:
            raise RuntimeError("private-authority-canary")

    operation = asyncio.create_task(oauth_browser.open_oauth_browser(URL, authorize=authorize))
    await wait_until(target.exists)
    active[0] = False
    Path(str(target) + ".exit").touch()
    with pytest.raises(oauth_browser.BrowserLaunchError) as caught:
        await asyncio.wait_for(operation, 2)
    details = "".join(traceback.format_exception(caught.value))
    assert "may have opened" in details and "canary" not in details
    assert_joined(processes)


@pytest.mark.parametrize("boundary", ["cancel", "deadline"])
async def test_final_guard_cannot_handoff_after_cancel_or_deadline(synthetic_launcher, monkeypatch, boundary):
    choose, _calls, processes = synthetic_launcher
    target = choose("success")
    writes, loop_errors = [], []
    loop = asyncio.get_running_loop()
    previous_handler = loop.get_exception_handler()
    loop.set_exception_handler(lambda _loop, context: loop_errors.append(context))
    original = oauth_browser.asyncio.create_subprocess_exec

    async def observe(*args, **kwargs):
        process = await original(*args, **kwargs)
        actual_write = process.stdin.write

        def write(data):
            writes.append(data)
            return actual_write(data)

        monkeypatch.setattr(process.stdin, "write", write)
        return process

    monkeypatch.setattr(oauth_browser.asyncio, "create_subprocess_exec", observe)
    monkeypatch.setattr(oauth_browser, "LAUNCH_TIMEOUT_SECONDS", .03)
    guards = 0

    def authorize():
        nonlocal guards
        guards += 1
        if guards == 2:
            if boundary == "cancel":
                asyncio.current_task().cancel("cancel before URL handoff")
            else:
                time.sleep(.08)

    operation = asyncio.create_task(oauth_browser.open_oauth_browser(URL, authorize=authorize))
    try:
        expected = asyncio.CancelledError if boundary == "cancel" else oauth_browser.BrowserLaunchError
        with pytest.raises(expected) as caught:
            await operation
        if boundary == "cancel":
            assert str(caught.value) == "cancel before URL handoff"
        await asyncio.sleep(0)
        assert not writes and not target.exists()
        assert "may have opened" not in "".join(getattr(caught.value, "__notes__", ()))
        assert not loop_errors
        assert_joined(processes)
    finally:
        loop.set_exception_handler(previous_handler)


async def test_publication_guard_cannot_return_success_after_deadline(synthetic_launcher, monkeypatch):
    choose, _calls, processes = synthetic_launcher
    target = choose("success")
    monkeypatch.setattr(oauth_browser, "LAUNCH_TIMEOUT_SECONDS", 1)
    guards = 0

    def authorize():
        nonlocal guards
        guards += 1
        if guards == 3:
            time.sleep(1.1)

    with pytest.raises(oauth_browser.BrowserLaunchError) as caught:
        await oauth_browser.open_oauth_browser(URL, authorize=authorize)
    assert guards == 3 and target.exists()
    assert "may have opened" in "".join(getattr(caught.value, "__notes__", ()))
    assert_joined(processes)


async def test_cancellation_while_closing_stdin_does_not_cancel_shared_protocol_future(synthetic_launcher, monkeypatch):
    choose, _calls, processes = synthetic_launcher
    choose("success")
    loop, loop_errors = asyncio.get_running_loop(), []
    previous_handler = loop.get_exception_handler()
    loop.set_exception_handler(lambda _loop, context: loop_errors.append(context))
    original = oauth_browser.asyncio.create_subprocess_exec

    async def observe(*args, **kwargs):
        process = await original(*args, **kwargs)
        actual_close = process.stdin.close
        cancelled = False

        def close():
            nonlocal cancelled
            actual_close()
            if not cancelled:
                cancelled = True
                asyncio.current_task().cancel("cancel closing browser stdin")

        monkeypatch.setattr(process.stdin, "close", close)
        return process

    monkeypatch.setattr(oauth_browser.asyncio, "create_subprocess_exec", observe)
    operation = asyncio.create_task(oauth_browser.open_oauth_browser(URL, authorize=lambda: None))
    try:
        with pytest.raises(asyncio.CancelledError, match="cancel closing browser stdin") as caught:
            await operation
        await asyncio.sleep(0)
        assert "may have opened" in "".join(getattr(caught.value, "__notes__", ()))
        assert not loop_errors
        assert_joined(processes)
    finally:
        loop.set_exception_handler(previous_handler)


@pytest.mark.skipif(not sys.platform.startswith("linux"), reason="Uses an owned fake Linux desktop executable")
async def test_packaged_child_execs_owned_launcher_pid_with_null_protocol_fds(synthetic_launcher, monkeypatch, tmp_path, capsys):
    _choose, calls, processes = synthetic_launcher
    target = tmp_path / "actual-helper.json"
    executable = tmp_path / "xdg-open"
    executable.write_text(f"#!{Path(sys.executable).resolve()}\n" +
        "import hashlib,json,os,pathlib,stat,sys\n" +
        f"pathlib.Path({str(target)!r}).write_text(json.dumps({{\"pid\":os.getpid(),\"hash\":hashlib.sha256(sys.argv[1].encode()).hexdigest(),"
        "\"stdin_empty\":os.read(0,1)==b\"\",\"stdout_character_device\":stat.S_ISCHR(os.fstat(1).st_mode)}))\n"
        "print('private-native-output-canary')\n")
    executable.chmod(0o755)
    monkeypatch.setenv("PATH", str(tmp_path))
    monkeypatch.setenv("DISPLAY", ":owned-fixture")
    await oauth_browser.open_oauth_browser(URL, authorize=lambda: None)
    data = json.loads(target.read_text())
    assert data["pid"] == processes[0].pid
    assert data["hash"] == hashlib.sha256(URL.encode()).hexdigest()
    assert data["stdin_empty"] and data["stdout_character_device"]
    assert calls[0][0] == oauth_browser._child_command()
    assert "canary" not in str(capsys.readouterr())
    assert_joined(processes)


@pytest.mark.skipif(not sys.platform.startswith("linux"), reason="Linux desktop availability is explicitly controlled")
async def test_packaged_child_without_desktop_refuses_before_handoff(synthetic_launcher, monkeypatch):
    _choose, _calls, processes = synthetic_launcher
    monkeypatch.delenv("DISPLAY", raising=False)
    monkeypatch.delenv("WAYLAND_DISPLAY", raising=False)
    with pytest.raises(oauth_browser.BrowserLaunchError, match="unavailable") as caught:
        await oauth_browser.open_oauth_browser(URL, authorize=lambda: None)
    assert "may have opened" not in "".join(getattr(caught.value, "__notes__", ()))
    assert_joined(processes)
