"""External composition uses owned POSIX terminal processes and private drafts."""

import json
import os
import select
import subprocess
import sys
import time
from pathlib import Path

import pytest

from henchman.cli.draft_editor import DraftEditorError, resolve_editor_argv


def test_editor_configuration_is_literal_argv_without_fallback(monkeypatch):
    monkeypatch.setenv("VISUAL", '"/path with spaces/editor" --wait "literal;$(echo nope)"')
    monkeypatch.setenv("EDITOR", "/ignored")
    assert resolve_editor_argv() == ("/path with spaces/editor", "--wait", "literal;$(echo nope)")
    monkeypatch.setenv("VISUAL", "'broken")
    with pytest.raises(DraftEditorError, match="configuration"):
        resolve_editor_argv()
    monkeypatch.delenv("VISUAL")
    monkeypatch.delenv("EDITOR")
    with pytest.raises(DraftEditorError, match="VISUAL or EDITOR"):
        resolve_editor_argv()


RUNNER = '''
import asyncio, fcntl, json, os, signal, sys, termios
from pathlib import Path
from henchman.cli.draft_editor import edit_draft
fcntl.ioctl(0, termios.TIOCSCTTY, 0)
root = Path(sys.argv[1])
mode = sys.argv[2]
original_group = os.tcgetpgrp(0)
original_attrs = termios.tcgetattr(0)
async def run():
    calls = 0
    def authorize():
        nonlocal calls
        calls += 1
        if mode == 'revoke' and calls > 1:
            raise ValueError('private-canary-do-not-echo')
    task = asyncio.create_task(edit_draft('original\\nUnicode café\\n', cwd=root, authorize=authorize,
        argv=(sys.executable, '-I', str(root / 'editor with spaces.py'), 'literal;$(touch NEVER)'), timeout=.2 if mode == 'timeout' else 8))
    if mode == 'cancel':
        while not (root / 'started').exists():
            await asyncio.sleep(.01)
        task.cancel('first cancellation')
        asyncio.get_running_loop().call_later(.01, task.cancel, 'second cancellation')
    try:
        result = await task
        report = {'text': result}
    except BaseException as error:
        report = {'error': type(error).__name__, 'message': str(error)}
    report['foreground_restored'] = os.tcgetpgrp(0) == original_group
    report['terminal_restored'] = termios.tcgetattr(0) == original_attrs
    report['calls'] = calls
    (root / 'receipt.json').write_text(json.dumps(report))
asyncio.run(run())
'''
EDITOR = '''
import json, os, signal, stat, sys, termios, time
from pathlib import Path
root = Path(__file__).parent
mode = (root / 'mode').read_text()
path = Path(sys.argv[-1])
assert not os.environ.get("OPENAI_API_KEY")
assert not os.environ.get("ANTHROPIC_API_KEY")
assert sys.argv[1] == 'literal;$(touch NEVER)'
assert os.tcgetpgrp(0) == os.getpgrp()
assert termios.tcgetattr(0)[3] & termios.ICANON
assert stat.S_IMODE(path.stat().st_mode) == 0o600
assert stat.S_IMODE(path.parent.stat().st_mode) == 0o700
(root / 'draft_path').write_text(str(path))
(root / 'started').write_text(str(os.getpid()))
assert path.read_text() == 'original\\nUnicode café\\n'
if mode in {'timeout', 'cancel'}:
    signal.signal(signal.SIGTERM, signal.SIG_IGN)
    time.sleep(30)
elif mode == 'nonzero':
    path.write_text('must not apply')
    sys.exit(9)
elif mode == 'symlink':
    path.unlink()
    path.symlink_to(root / 'private')
elif mode == 'hardlink':
    path.unlink()
    os.link(root / 'private', path)
elif mode == 'oversize':
    path.write_bytes(b'x' * (1024 * 1024 + 1))
elif mode == 'invalid':
    path.write_bytes(b'\\xff')
else:
    print('EDITOR_READY', flush=True)
    line = input()
    path.write_text('edited\\n' + line + '\\nUnicode café\\n')
'''


@pytest.mark.skipif(os.name != "posix", reason="POSIX foreground terminal contract")
@pytest.mark.parametrize("mode", ["success", "nonzero", "symlink", "hardlink", "oversize", "invalid", "timeout", "cancel", "revoke"])
def test_real_pty_editor_owns_terminal_and_always_restores_it(tmp_path, mode, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "private-parent-provider-credential")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "private-parent-other-provider-credential")
    import pty

    (tmp_path / "mode").write_text(mode)
    (tmp_path / "private").write_text("private-canary-do-not-echo")
    (tmp_path / "editor with spaces.py").write_text(EDITOR)
    master, slave = pty.openpty()
    process = subprocess.Popen([sys.executable, "-c", RUNNER, str(tmp_path), mode],
                               stdin=slave, stdout=slave, stderr=slave, start_new_session=True)
    os.close(slave)
    output = b""
    sent = False
    try:
        deadline = time.monotonic() + 20
        while process.poll() is None:
            assert time.monotonic() < deadline, output.decode(errors="replace")
            if select.select([master], [], [], .05)[0]:
                try:
                    output += os.read(master, 65536)
                except OSError:
                    break
            if b"EDITOR_READY" in output and not sent:
                os.write(master, b"terminal input\n")
                sent = True
        process.wait(timeout=5)
        assert process.returncode == 0, output.decode(errors="replace")
        receipt = json.loads((tmp_path / "receipt.json").read_text())
        assert receipt["foreground_restored"] and receipt["terminal_restored"]
        if mode == "success":
            assert receipt["text"] == "edited\nterminal input\nUnicode café\n"
        elif mode == "cancel":
            assert receipt["error"] == "CancelledError" and receipt["message"] == "first cancellation"
        else:
            assert receipt["error"] == "DraftEditorError"
        assert "private-canary-do-not-echo" not in str(receipt)
        assert not (tmp_path / "NEVER").exists()
        if (tmp_path / "draft_path").exists():
            assert not Path((tmp_path / "draft_path").read_text()).parent.exists()
        if (tmp_path / "started").exists():
            with pytest.raises(ProcessLookupError):
                os.kill(int((tmp_path / "started").read_text()), 0)
    finally:
        if process.poll() is None:
            process.kill()
        process.wait(timeout=5)
        os.close(master)


@pytest.mark.parametrize("setting", [
    {"filesystem_read_roots": []}, {"filesystem_write_roots": []},
    {"network_access": "disabled"}, {"network_allowed_hosts": []},
])
async def test_editor_denies_restricted_policy_before_process_start(setting, tmp_path):
    from types import SimpleNamespace

    from henchman.cli.draft_editor import require_editor_idle
    from henchman.config.schema import Settings

    frontend = SimpleNamespace(settings=Settings(tools=setting), project_root=tmp_path)
    with pytest.raises(DraftEditorError, match="unrestricted"):
        require_editor_idle(frontend)


@pytest.mark.skipif(os.name != "posix", reason="POSIX draft validation path")
async def test_invalid_utf8_and_oversize_input_fail_before_private_file(tmp_path, monkeypatch):
    from henchman.cli import draft_editor

    def forbidden(*_args, **_kwargs):
        raise AssertionError("must not create temporary state")
    monkeypatch.setattr(draft_editor.tempfile, "TemporaryDirectory", forbidden)
    for value in ("\ud800", "x" * (draft_editor.MAX_DRAFT_BYTES + 1)):
        with pytest.raises(DraftEditorError, match="UTF-8"):
            await draft_editor.edit_draft(value, cwd=tmp_path, authorize=lambda: None)


async def test_binding_denies_replacement_before_any_editor_start(tmp_path):
    from types import SimpleNamespace

    from henchman.cli.draft_editor import DraftBinding
    from henchman.config.schema import Settings

    project = tmp_path / "project"
    project.mkdir()
    frontend = SimpleNamespace(project_root=project, settings=Settings())
    binding = DraftBinding.capture(frontend)
    project.rename(tmp_path / "prior")
    project.mkdir()
    with pytest.raises(DraftEditorError, match="project"):
        binding.check(frontend)


async def test_non_posix_has_explicit_refusal_before_temp_or_process(tmp_path, monkeypatch):
    from henchman.cli import draft_editor

    monkeypatch.setattr(draft_editor.os, "tcsetpgrp", None, raising=False)
    # Do not mutate process-wide os.name, which changes pathlib's platform type.
    monkeypatch.delattr(draft_editor.os, "tcsetpgrp")
    with pytest.raises(DraftEditorError, match="POSIX"):
        await draft_editor.edit_draft("keep", cwd=tmp_path, authorize=lambda: None)


CONTROL_RUNNER = r'''
import asyncio, fcntl, json, os, sys, termios, time
from pathlib import Path
from henchman.cli import draft_editor
fcntl.ioctl(0, termios.TIOCSCTTY, 0)
root = Path(sys.argv[1])
mode = sys.argv[2]
original_group = os.tcgetpgrp(0)
original_attrs = termios.tcgetattr(0)
original_write = os.write
# Observe a scheduling interleaving after the permit reaches the real child:
# the parent has no further opportunity to revoke a completed exec effect.
def observe_permit(fd, data):
    result = original_write(fd, data)
    if data == b'g':
        until = time.monotonic() + 1.0
        while not (root / 'editor_effect').exists() and time.monotonic() < until:
            time.sleep(.005)
    return result
draft_editor.os.write = observe_permit
async def run():
    calls = 0
    def authorize():
        nonlocal calls
        calls += 1
        if calls == 2:
            if mode == 'cancel':
                asyncio.current_task().cancel('original requested cancellation')
            elif mode == 'deadline':
                time.sleep(.1)
        if calls == 3 and mode == 'finaldeadline':
            time.sleep(1)
    try:
        value = await draft_editor.edit_draft('keep original', cwd=root, authorize=authorize,
            argv=(sys.executable, '-I', str(root / 'editor.py')), timeout=.06 if mode == 'deadline' else (.8 if mode == 'finaldeadline' else 5))
        report = {'value': value}
    except BaseException as error:
        report = {'error': type(error).__name__, 'message': str(error)}
    report.update(calls=calls, effect=(root / 'editor_effect').exists(),
                  foreground_restored=os.tcgetpgrp(0) == original_group,
                  terminal_restored=termios.tcgetattr(0) == original_attrs)
    (root / 'receipt.json').write_text(json.dumps(report))
asyncio.run(run())
'''
CONTROL_EDITOR = r'''
import sys
from pathlib import Path
root = Path(__file__).parent
(root / 'editor_effect').write_text('started')
Path(sys.argv[-1]).write_text('edited')
'''

@pytest.mark.skipif(os.name != 'posix', reason='owned POSIX PTY probe')
@pytest.mark.parametrize('mode', ['cancel', 'deadline', 'finaldeadline'])
def test_editor_refuses_pending_control_before_exec_and_publication(tmp_path, mode):
    import pty
    (tmp_path / 'editor.py').write_text(CONTROL_EDITOR)
    master, slave = pty.openpty()
    child = subprocess.Popen([sys.executable, '-c', CONTROL_RUNNER, str(tmp_path), mode],
                             stdin=slave, stdout=slave, stderr=slave, start_new_session=True)
    os.close(slave)
    output = b''
    try:
        end = time.monotonic() + 12
        while child.poll() is None:
            assert time.monotonic() < end, output.decode(errors='replace')
            if select.select([master], [], [], .05)[0]:
                try:
                    output += os.read(master, 65536)
                except OSError:
                    break
        child.wait(timeout=3)
        assert child.returncode == 0, output.decode(errors='replace')
        receipt = json.loads((tmp_path / 'receipt.json').read_text())
        assert receipt['foreground_restored'] and receipt['terminal_restored'], receipt
        if mode == 'cancel':
            assert receipt.get('error') == 'CancelledError', receipt
            assert receipt['message'] == 'original requested cancellation', receipt
        else:
            assert receipt.get('error') == 'DraftEditorError', receipt
        if mode != 'finaldeadline':
            assert not receipt['effect'], receipt
    finally:
        if child.poll() is None:
            child.kill()
        child.wait(timeout=3)
        os.close(master)


CLASSIC_RUNNER = r'''
import asyncio, fcntl, json, os, shlex, sys, termios
from pathlib import Path
from henchman.cli.repl import Repl, ReplConfig
from henchman.config.schema import Settings
from henchman.providers.base import ModelProvider
fcntl.ioctl(0, termios.TIOCSCTTY, 0)
root = Path(sys.argv[1])
os.chdir(root)
os.environ['TERM'] = sys.argv[2]
os.environ['VISUAL'] = shlex.join((sys.executable, '-I', str(root / 'editor with spaces.py'), 'literal;$(touch NEVER)'))
original_group = os.tcgetpgrp(0)
original_attrs = termios.tcgetattr(0)
def snapshot():
    attrs = termios.tcgetattr(0)
    return [*attrs[:6], [v.hex() if isinstance(v, bytes) else v for v in attrs[6]]]
snapshots = {'initial': snapshot()}
use_editor = sys.argv[3] == 'editor'
class OfflineProvider(ModelProvider):
    name = 'offline'
    async def chat_completion_stream(self, *args, **kwargs):
        raise AssertionError('No model request is permitted')
        yield
async def run():
    repl = Repl(provider=OfflineProvider(), settings=Settings(rag={'enabled': False}),
        config=ReplConfig(auto_save=False, history_file=root / 'history'))
    snapshots['after_repl_init'] = snapshot()
    from henchman.cli import input_handler
    real_edit = input_handler.edit_draft
    async def observed_edit(*args, **kwargs):
        snapshots['before_edit'] = snapshot()
        try:
            return await real_edit(*args, **kwargs)
        finally:
            snapshots['after_edit'] = snapshot()
    input_handler.edit_draft = observed_edit
    session = repl.input_handler.prompt_session
    signalled = False
    def ready(_app):
        nonlocal signalled
        if not signalled:
            signalled = True
            os.write(1, b'COMPOSER_READY\n')
    session.app.after_render += ready
    prompt = asyncio.create_task(session.prompt_async('> '))
    try:
        async with asyncio.timeout(10):
            if use_editor:
                while repl.input_handler._editor_task is None:
                    await asyncio.sleep(.01)
                await repl.input_handler._editor_task
            else:
                while session.default_buffer.text != 'original\nUnicode café\n':
                    await asyncio.sleep(.01)
            snapshots['after_edit_task_or_control'] = snapshot()
        result = session.default_buffer.text
        assert not prompt.done() and repl._turn_worker is None
        prompt.cancel()
        await asyncio.gather(prompt, return_exceptions=True)
        snapshots['after_prompt_cancel'] = snapshot()
    finally:
        await repl.aclose()
        if not prompt.done():
            prompt.cancel()
        await asyncio.gather(prompt, return_exceptions=True)
    snapshots['after_repl_close'] = snapshot()
    report = dict(snapshots=snapshots, text=result, foreground_restored=os.tcgetpgrp(0) == original_group,
                  terminal_restored=termios.tcgetattr(0) == original_attrs)
    (root / 'classic-receipt.json').write_text(json.dumps(report))
asyncio.run(run())
'''


@pytest.mark.skipif(os.name != "posix", reason="actual POSIX classic REPL terminal")
@pytest.mark.parametrize("terminal_kind", ["xterm-256color", "dumb"])
@pytest.mark.parametrize("use_editor", [True, False])
def test_classic_f11_real_pty_restores_prompt_without_submitting(tmp_path, terminal_kind, use_editor):
    import fcntl
    import pty
    import struct
    import termios

    (tmp_path / "mode").write_text("success")
    (tmp_path / "editor with spaces.py").write_text(EDITOR)
    master, slave = pty.openpty()
    fcntl.ioctl(slave, termios.TIOCSWINSZ, struct.pack("HHHH", 24, 80, 0, 0))
    child = subprocess.Popen([sys.executable, "-c", CLASSIC_RUNNER, str(tmp_path), terminal_kind, "editor" if use_editor else "control"],
                             stdin=slave, stdout=slave, stderr=slave, start_new_session=True)
    os.close(slave)
    output = b""
    composed = answered = False
    try:
        deadline = time.monotonic() + 20
        while child.poll() is None:
            assert time.monotonic() < deadline, output.decode(errors="replace")
            if select.select([master], [], [], .05)[0]:
                try:
                    chunk = os.read(master, 65536)
                    output += chunk
                    if b"\x1b[6n" in chunk:
                        os.write(master, b"\x1b[1;1R")
                except OSError:
                    break
            if (b"COMPOSER_READY" in output or (terminal_kind == "dumb" and b"> " in output)) and not composed:
                os.write(master, ("\x1b[200~original\nUnicode café\n\x1b[201~" + ("\x1b[23~" if use_editor else "")).encode())
                composed = True
            if b"EDITOR_READY" in output and not answered:
                os.write(master, b"terminal input\n")
                answered = True
        child.wait(timeout=3)
        assert child.returncode == 0, output.decode(errors="replace")
        report = json.loads((tmp_path / "classic-receipt.json").read_text())
        print(json.dumps({"terminal": terminal_kind, "use_editor": use_editor, "report": report}), flush=True)
        assert report["text"] == ("edited\nterminal input\nUnicode café\n" if use_editor else "original\nUnicode café\n")
        assert report["foreground_restored"]
        assert report["terminal_restored"], report["snapshots"]
        assert not (tmp_path / "history").exists()
    finally:
        if child.poll() is None:
            child.kill()
        child.wait(timeout=3)
        os.close(master)
