"""Synthetic key-to-sampled-pixels probe in an actual native VTE widget.

The X display is virtual. This measures a conservative command-to-sample bound,
not a physical display, input device, assistive technology or live model.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

import gi
gi.require_version('Gtk', '3.0')
gi.require_version('Gdk', '3.0')
gi.require_version('GdkX11', '3.0')
gi.require_version('Vte', '2.91')
from gi.repository import Gdk, GdkX11, GLib, Gtk, Pango, Vte

root, source = Path(sys.argv[1]), Path(sys.argv[2])
columns, rows, history = map(int, sys.argv[3:6])
root.mkdir(mode=0o700, parents=True, exist_ok=False)
result = {
    'version': 1, 'viewport': [columns, rows], 'history': history,
    'source': str(source), 'status': 'RUNNING', 'calibration': {},
    'input': [{'index': n, 'status': 'NOT_RUN'} for n in range(20)],
    'cancel': [{'index': n, 'status': 'NOT_RUN'} for n in range(20)],
    'method': 'monotonic time before xdotool launch to first matching sampled native window pixels',
    'limits': ['Virtual X11 software display', 'Includes xdotool/process launch and sampling overhead',
               'Scripted 1-second cleanup, no provider or model', 'Shared host without affinity or load isolation',
               'Calibration excluded; exactly20 measured attempts per action, no replacement',
               'No physical device/monitor, clipboard, remote, IME, screen reader or human qualification'],
}


def save() -> None:
    temporary = root / 'receipt.tmp'
    temporary.write_text(json.dumps(result, indent=2) + '\n')
    temporary.replace(root / 'receipt.json')


save()
window = Gtk.Window(title='Henchman owned native VTE measurement')
window.set_decorated(False)
terminal = Vte.Terminal()
terminal.set_font(Pango.FontDescription('Monospace 12'))
terminal.set_size(columns, rows)
terminal.set_cursor_blink_mode(Vte.CursorBlinkMode.OFF)
terminal.set_text_blink_mode(Vte.TextBlinkMode.NEVER)
window.add(terminal)
window.show_all()
child: int | None = None
child_status: int | None = None
spawn_error: str | None = None


def pump() -> None:
    for _ in range(200):
        if not Gtk.events_pending():
            return
        Gtk.main_iteration_do(False)


def wait(predicate, timeout: float = 10) -> int:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        pump()
        if spawn_error is not None:
            raise RuntimeError(spawn_error)
        if child_status is not None:
            raise RuntimeError('Owned app exited during observation: ' + str(child_status))
        if predicate():
            return time.monotonic_ns()
        time.sleep(0.001)
    raise TimeoutError('Required observation not available')


def spawned(_terminal, pid, error, _data):
    global child, spawn_error
    if error:
        spawn_error = str(error)
    else:
        child = pid
        birth = Path(f'/proc/{pid}/stat').read_text().rsplit(')', 1)[1].split()[19]
        (root / 'owned-child.json').write_text(json.dumps({'pid': pid, 'birth': birth}))


def exited(_terminal, status):
    global child_status
    child_status = status


terminal.connect('child-exited', exited)
env = {'PATH': os.environ['PATH'], 'HOME': str(root), 'USERPROFILE': str(root),
       'PYTHONPATH': str(source) + ':' + str(source / 'src'), 'LANG': 'C.UTF-8',
       'TERM': 'xterm-256color', 'DISPLAY': os.environ['DISPLAY']}
terminal.spawn_async(Vte.PtyFlags.DEFAULT, str(root),
    ['/home/matthew/mlg-cli/.venv/bin/python', str(Path(__file__).with_name('probe_app.py')), str(root), str(history)],
    [key + '=' + value for key, value in env.items()], GLib.SpawnFlags.DEFAULT,
    None, None, -1, None, spawned, None)


def text() -> str:
    return terminal.get_text_format(Vte.Format.TEXT) or ''


def command(*args: str) -> int:
    started = time.monotonic_ns()
    subprocess.run(['xdotool', *args], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, timeout=5)
    return started


def key(name: str) -> int:
    return command('key', '--clearmodifiers', '--delay', '0', name)


def pixels(rect: tuple[int, int, int, int]) -> bytes:
    image = Gdk.pixbuf_get_from_window(terminal.get_window(), *rect)
    if image is None:
        raise RuntimeError('Native window pixels unavailable')
    data = image.get_pixels()
    width = image.get_width() * image.get_n_channels()
    stride = image.get_rowstride()
    return b''.join(data[y * stride:y * stride + width] for y in range(image.get_height()))


def screenshot(name: str) -> None:
    allocation = terminal.get_allocation()
    image = Gdk.pixbuf_get_from_window(terminal.get_window(), 0, 0, allocation.width, allocation.height)
    image.savev(str(root / name), 'png', [], [])


def has_input(path: str, value: str) -> bool:
    try:
        return json.loads((root / path).read_text())['input'] == value
    except (FileNotFoundError, json.JSONDecodeError):
        return False


def start_work(value: str) -> None:
    command('type', '--clearmodifiers', '--delay', '0', value)
    # Different X clients may be scheduled before the preceding client's whole
    # event batch. Observe the complete composer before the distinct submit.
    wait(lambda: value in text().splitlines()[input_row])
    key('Return')
    wait(lambda: has_input('worker-ready.json', value))


def finish_work(value: str) -> None:
    wait(lambda: has_input('worker-finished.json', value))
    wait(lambda: text().splitlines()[-1].startswith('Cancelled'))


def interrupted(_signum, _frame):
    raise KeyboardInterrupt('Owned supervisor requested shutdown')


signal.signal(signal.SIGTERM, interrupted)

try:
    wait(lambda: (root / 'app-ready.json').exists() and 'Henchman' in text(), 35)
    ready = json.loads((root / 'app-ready.json').read_text())
    assert ready['size'] == [columns, rows]
    assert (terminal.get_column_count(), terminal.get_row_count()) == (columns, rows)
    xid = GdkX11.X11Window.get_xid(window.get_window())
    command('windowfocus', '--sync', str(xid))
    char_w, char_h = terminal.get_char_width(), terminal.get_char_height()
    padding = terminal.get_style_context().get_padding(Gtk.StateFlags.NORMAL)
    input_row = ready['input_region'][1] + 1
    key('x')
    wait(lambda: 'x' in text().splitlines()[input_row])
    # Calibration is excluded from the fixed denominator. Allow both app and
    # emulator frames to settle before learning the expected glyph pixels.
    until = time.monotonic() + 0.2
    while time.monotonic() < until:
        pump()
        time.sleep(0.001)
    input_column = text().splitlines()[input_row].index('x')
    input_rect = (padding.left + input_column * char_w, padding.top + input_row * char_h, 2 * char_w, char_h)
    target_input = pixels(input_rect)
    screenshot('calibration-input.png')
    key('BackSpace')
    wait(lambda: 'x' not in text().splitlines()[input_row] and pixels(input_rect) != target_input)
    empty_input = pixels(input_rect)
    assert empty_input != target_input
    result['calibration']['input'] = {'rect': input_rect, 'target_sha256': hashlib.sha256(target_input).hexdigest(),
                                      'empty_sha256': hashlib.sha256(empty_input).hexdigest()}
    result['terminal'] = {'vte': [Vte.get_major_version(), Vte.get_minor_version(), Vte.get_micro_version()],
                          'gtk': [Gtk.get_major_version(), Gtk.get_minor_version(), Gtk.get_micro_version()],
                          'font': 'Monospace12', 'cell': [char_w, char_h], 'xid': xid}
    save()
    for trial in result['input']:
        trial['status'] = 'RUNNING'
        save()
        assert pixels(input_rect) != target_input
        start = key('x')
        seen = wait(lambda: 'x' in text().splitlines()[input_row] and pixels(input_rect) == target_input, 2)
        trial.update(status='PASS', elapsed_ms=(seen - start) / 1_000_000)
        key('BackSpace')
        wait(lambda: 'x' not in text().splitlines()[input_row] and pixels(input_rect) == empty_input, 2)
        save()
    start_work('calibration')
    key('Escape')
    wait(lambda: 'Cancelling' in text().splitlines()[-1])
    until = time.monotonic() + 0.2
    while time.monotonic() < until:
        pump()
        time.sleep(0.001)
    assert 'Cancelling' in text().splitlines()[-1]
    cancel_rect = (padding.left, padding.top + (rows - 1) * char_h, 12 * char_w, char_h)
    target_cancel = pixels(cancel_rect)
    screenshot('calibration-cancel.png')
    result['calibration']['cancel'] = {'rect': cancel_rect, 'text': text().splitlines()[-1],
                                       'target_sha256': hashlib.sha256(target_cancel).hexdigest()}
    finish_work('calibration')
    assert pixels(cancel_rect) != target_cancel
    for trial in result['cancel']:
        value = 'probe' + str(trial['index'])
        start_work(value)
        trial['status'] = 'RUNNING'
        save()
        assert pixels(cancel_rect) != target_cancel
        start = key('Escape')
        seen = wait(lambda: 'Cancelling' in text().splitlines()[-1] and pixels(cancel_rect) == target_cancel, 2)
        trial.update(status='PASS', elapsed_ms=(seen - start) / 1_000_000)
        finish_work(value)
        trial['joined_cleanup_ms'] = (time.monotonic_ns() - start) / 1_000_000
        save()
    for kind, threshold in [('input', 100), ('cancel', 250)]:
        measured = sorted(trial['elapsed_ms'] for trial in result[kind])
        p95 = measured[math.ceil(0.95 * len(measured)) - 1]
        result[kind + '_summary'] = {'denominator': 20, 'p95_ms': p95, 'max_ms': max(measured),
                                    'criterion_ms': threshold, 'criterion_passed': p95 < threshold}
    result['status'] = 'COMPLETE'
except BaseException as error:
    result['status'] = 'INCOMPLETE'
    result['error'] = type(error).__name__ + ': ' + str(error)
    for kind in ('input', 'cancel'):
        for trial in result[kind]:
            if trial['status'] == 'RUNNING':
                trial['status'] = 'FAILED'
    (root / 'terminal-on-failure.txt').write_text(text())
    screenshot('failure.png')
finally:
    if child is not None and child_status is None:
        try:
            os.kill(child, signal.SIGTERM)
        except ProcessLookupError:
            pass
        deadline = time.monotonic() + 5
        while child_status is None and time.monotonic() < deadline:
            pump()
            time.sleep(0.001)
        if child_status is None:
            os.kill(child, signal.SIGKILL)
            deadline = time.monotonic() + 5
            while child_status is None and time.monotonic() < deadline:
                pump()
                time.sleep(0.001)
    result['app_joined'] = child is None or child_status is not None
    window.destroy()
    save()
raise SystemExit(0 if result['status'] == 'COMPLETE' and result['app_joined'] else 1)
