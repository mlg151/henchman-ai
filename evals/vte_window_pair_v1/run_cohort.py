"""Execute the predeclared native comparison once, preserving every outcome."""
from __future__ import annotations

import hashlib
import json
import os
import signal
import subprocess
import time
from pathlib import Path

root = Path(__file__).resolve().parent
plan = json.loads((root / 'frozen-plan.json').read_text())
result_path = root / 'cohort-results.json'
assert not result_path.exists(), 'A cohort may not replace earlier observations'


def verify_inputs() -> None:
    for name, expected in plan['harness_sha256'].items():
        assert hashlib.sha256((root / name).read_bytes()).hexdigest() == expected, name
    for arm in plan['arms'].values():
        source = Path(arm['source'])
        for row in arm['files']:
            path = source / row['path']
            data = os.readlink(path).encode() if row['kind'] == 'symlink' else path.read_bytes()
            assert hashlib.sha256(data).hexdigest() == row['sha256'], str(path)


def save() -> None:
    temporary = result_path.with_suffix('.tmp')
    temporary.write_text(json.dumps(result, indent=2) + '\n')
    temporary.replace(result_path)


def interrupted(_signum, _frame) -> None:
    raise KeyboardInterrupt('Cohort interrupted; owned scenario must settle')


signal.signal(signal.SIGTERM, interrupted)
verify_inputs()
result = {
    'plan_sha256': hashlib.sha256((root / 'frozen-plan.json').read_bytes()).hexdigest(),
    'started_utc': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
    'status': 'RUNNING',
    'cases': [dict(case, status='NOT_RUN') for case in plan['cases']],
}
save()
try:
    for case in result['cases']:
        source = plan['arms'][case['arm']]['source']
        case['status'] = 'RUNNING'
        case['host_load_before'] = os.getloadavg()
        started = time.monotonic()
        save()
        print('START', case['name'], flush=True)
        child = None
        try:
            with (root / (case['name'] + '-driver.log')).open('w') as log:
                child = subprocess.Popen(
                    ['/usr/bin/python3', str(root / 'run_measure.py'), case['name'], source,
                     str(case['columns']), str(case['rows']), str(case['history'])],
                    stdout=log, stderr=subprocess.STDOUT,
                )
                case['returncode'] = child.wait()
        finally:
            if child is not None and child.poll() is None:
                child.terminate()
                child.wait(timeout=45)
            case['elapsed_seconds'] = time.monotonic() - started
            case['host_load_after'] = os.getloadavg()
        scenario_receipt = root / case['name'] / 'receipt.json'
        supervisor_receipt = root / (case['name'] + '-supervisor.json')
        if scenario_receipt.exists():
            case['receipt'] = json.loads(scenario_receipt.read_text())
        if supervisor_receipt.exists():
            case['supervisor'] = json.loads(supervisor_receipt.read_text())
        case['status'] = 'COMPLETE' if case['returncode'] == 0 else 'FAILED'
        save()
        print('END', case['name'], case['status'],
              json.dumps({key: case.get('receipt', {}).get(key) for key in ('input_summary', 'cancel_summary')}), flush=True)
        if not (case.get('supervisor', {}).get('measurement_joined')
                and case.get('supervisor', {}).get('xvfb_joined')
                and case.get('supervisor', {}).get('app_identity_absent') is True):
            raise RuntimeError('Owned cleanup did not complete; later cases remain NOT_RUN')
    verify_inputs()
    result['status'] = 'COMPLETE'
except BaseException as error:
    result['status'] = 'INCOMPLETE'
    result['error'] = type(error).__name__ + ': ' + str(error)
    for case in result['cases']:
        if case['status'] == 'RUNNING':
            case['status'] = 'FAILED'
finally:
    result['finished_utc'] = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
    save()

raise SystemExit(0 if result['status'] == 'COMPLETE' else 1)
