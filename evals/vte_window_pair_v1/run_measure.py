"""One fixed native scenario; owns and joins the display and measurement child."""
from __future__ import annotations

import json
import os
import select
import signal
import subprocess
import sys
import time
from pathlib import Path

root = Path(__file__).resolve().parent
destination = root / sys.argv[1]
source = Path(sys.argv[2]).resolve(strict=True)
columns, rows, history = sys.argv[3:6]
assert not destination.exists()
receipt_path = root / (destination.name + '-supervisor.json')
assert not receipt_path.exists()
receipt: dict = {'scenario': destination.name, 'source': str(source), 'status': 'STARTING'}
server = None
process = None
readfd = None
writefd = None
code = 1


def identity(pid: int) -> dict | None:
    try:
        fields = Path(f'/proc/{pid}/stat').read_text().rsplit(')', 1)[1].split()
        return {'pid': pid, 'birth': fields[19], 'state': fields[0]}
    except FileNotFoundError:
        return None


def save() -> None:
    receipt_path.write_text(json.dumps(receipt, indent=2) + '\n')


def join_owned(child: subprocess.Popen | None, label: str) -> None:
    if child is None:
        receipt[label + '_joined'] = True
        return
    if child.poll() is None:
        child.terminate()
        try:
            child.wait(timeout=15)
        except subprocess.TimeoutExpired:
            child.kill()
            child.wait(timeout=5)
    receipt[label + '_returncode'] = child.returncode
    receipt[label + '_joined'] = child.poll() is not None


def clear_owned_app() -> None:
    owner_path = destination / 'owned-child.json'
    if not owner_path.exists():
        receipt['app_identity_absent'] = None
        return
    owner = json.loads(owner_path.read_text())
    receipt['app_identity'] = owner
    current = identity(owner['pid'])
    if current and current['birth'] == owner['birth']:
        try:
            fd = os.pidfd_open(owner['pid'])
        except ProcessLookupError:
            fd = None
        if fd is not None:
            try:
                current = identity(owner['pid'])
                if current and current['birth'] == owner['birth']:
                    signal.pidfd_send_signal(fd, signal.SIGKILL)
                    receipt['app_emergency_kill'] = True
            finally:
                os.close(fd)
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            current = identity(owner['pid'])
            if current is None or current['birth'] != owner['birth']:
                break
            time.sleep(0.02)
    current = identity(owner['pid'])
    receipt['app_identity_absent'] = current is None or current['birth'] != owner['birth']


def interrupted(_signum, _frame) -> None:
    raise KeyboardInterrupt('Owned supervisor requested shutdown')


signal.signal(signal.SIGTERM, interrupted)
started = time.monotonic()
save()
try:
    readfd, writefd = os.pipe()
    env = dict(os.environ, LIBGL_ALWAYS_SOFTWARE='1', GALLIUM_DRIVER='llvmpipe')
    with (root / (destination.name + '-xvfb.log')).open('w') as log:
        server = subprocess.Popen(
            ['Xvfb', '-displayfd', str(writefd), '-screen', '0', '2000x1400x24', '-nolisten', 'tcp'],
            pass_fds=(writefd,), env=env, stdout=subprocess.DEVNULL, stderr=log,
        )
    receipt['xvfb_identity'] = identity(server.pid)
    os.close(writefd)
    writefd = None
    assert select.select([readfd], [], [], 10)[0], 'Owned X display did not start'
    display = os.read(readfd, 64).decode().strip()
    assert display.isdigit(), 'Invalid owned display response'
    os.close(readfd)
    readfd = None
    with (root / (destination.name + '.log')).open('w') as log:
        process = subprocess.Popen(
            ['/usr/bin/python3', str(root / 'measure.py'), str(destination), str(source), columns, rows, history],
            env=dict(env, DISPLAY=':' + display), stdout=log, stderr=subprocess.STDOUT,
        )
        receipt['measurement_identity'] = identity(process.pid)
        receipt['status'] = 'RUNNING'
        save()
        code = process.wait(timeout=200)
    receipt['status'] = 'COMPLETE' if code == 0 else 'FAILED'
except BaseException as error:
    receipt['status'] = 'FAILED'
    receipt['error'] = type(error).__name__ + ': ' + str(error)
finally:
    for fd in (readfd, writefd):
        if fd is not None:
            os.close(fd)
    try:
        join_owned(process, 'measurement')
        clear_owned_app()
    finally:
        join_owned(server, 'xvfb')
        receipt['elapsed_seconds'] = time.monotonic() - started
        save()

print(json.dumps(receipt), flush=True)
if not (receipt.get('measurement_joined') and receipt.get('xvfb_joined')
        and receipt.get('app_identity_absent') is True):
    code = 1
raise SystemExit(code)
