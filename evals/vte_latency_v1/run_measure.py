"""Run one fixed prototype scenario under an owned software X display."""
import json
import os
import select
import signal
import subprocess
import sys
from pathlib import Path

root = Path(__file__).parent
destination = root / sys.argv[1]
columns, rows, history = sys.argv[2:5]
assert not destination.exists()
readfd, writefd = os.pipe()
env = dict(os.environ, LIBGL_ALWAYS_SOFTWARE='1', GALLIUM_DRIVER='llvmpipe')
with open(root / (destination.name + '-xvfb.log'), 'w') as serverlog:
    server = subprocess.Popen(['Xvfb', '-displayfd', str(writefd), '-screen', '0', '2000x1400x24', '-nolisten', 'tcp'],
                              pass_fds=(writefd,), env=env, stdout=subprocess.DEVNULL, stderr=serverlog)
os.close(writefd)
try:
    assert select.select([readfd], [], [], 10)[0], 'owned X display did not start'
    with os.fdopen(readfd) as read:
        display = read.readline().strip()
    assert display.isdigit()
    with open(root / (destination.name + '.log'), 'w') as log:
        process = subprocess.Popen(['/usr/bin/python3', str(root / 'measure.py'), str(destination),
                                 '/home/matthew/.cache/henchman-release-qualification/0682889-source311-1gn95mji',
                                 columns, rows, history],
                                env=dict(env, DISPLAY=':' + display), stdout=log, stderr=subprocess.STDOUT)
        try:
            code = process.wait(timeout=200)
        except BaseException:
            process.terminate()
            try:
                process.wait(timeout=15)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)
                owned = destination / 'owned-child.json'
                if owned.exists():
                    owner = json.loads(owned.read_text())
                    try:
                        current = Path(f"/proc/{owner['pid']}/stat").read_text().rsplit(')', 1)[1].split()[19]
                        if current == owner['birth']:
                            os.kill(owner['pid'], signal.SIGKILL)
                    except FileNotFoundError:
                        pass
            raise
    print('scenario exit', code)
finally:
    server.terminate()
    server.wait(timeout=5)
if (destination / 'receipt.json').exists():
    receipt = json.loads((destination / 'receipt.json').read_text())
    print(json.dumps({k:v for k,v in receipt.items() if k not in ('input','cancel','calibration')}))
raise SystemExit(code)
