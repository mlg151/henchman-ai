# Archived native VTE latency probe v1

These three scripts are **exact executed copies**, not a portable benchmark
framework. Their SHA256 values are in the
[2026-11-08 baseline report](../../docs/evaluations/2026-11-08-vte-latency-v1.md)
and its [full receipt](../../docs/evaluations/2026-11-08-vte-latency-v1.json).
The source was `06828897485caad09899606e98d8318d0ff9c715`. All 240 observations
were retained; three long-history cancellation p95 criteria failed. No model,
provider, browser or account is used by this scripted workload.

`run_measure.py` owns an Xvfb display and waits for the measurement process,
then joins Xvfb. `measure.py` creates an actual GTK/VTE terminal, launches the
production-control fixture, injects X11 keys with `xdotool`, calibrates native
pixel crops, records fixed trials, and closes/joins the app.
`probe_app.py` uses the source checkout's `InteractionApp` and production
Textual controls, with a deliberately blocked worker and one-second cleanup.
These scripts execute at module top level: **do not import them as libraries**.

The historical environment had Linux, VTE 0.84.0, GTK 3.24.52, Xvfb, `xdotool`,
PyGObject with Gtk/Gdk/GdkX11/Vte typelibs, and a project Python environment with
the development dependencies needed by `tests.cli.ui_scenarios`. The supervisor
uses `/usr/bin/python3` for GI and requests software rendering with
`LIBGL_ALWAYS_SOFTWARE=1` and `GALLIUM_DRIVER=llvmpipe`. The captured results do
not establish compatibility with other versions or operating systems.

For an intentional future measurement, first prepare a separate, clean source
checkout and application Python environment. Preserve the chosen source commit,
dependency versions, host/load information and modified script hashes in a new
manifest **before** running. Copy the archive into a new private working
directory: outputs are written beside the copied supervisor, and each scenario
directory must not already exist. Do not run in this archive or overwrite the
historical artifact directory.

```bash
repro_dir=$(mktemp -d)
chmod 700 "$repro_dir"
cp evals/vte_latency_v1/measure.py evals/vte_latency_v1/probe_app.py \
  evals/vte_latency_v1/run_measure.py "$repro_dir/"
```

Two literals bind the original host. Repoint them only in the disposable copies:

| Copy | Original literal | Replacement |
|---|---|---|
| `run_measure.py` | `/home/matthew/.cache/henchman-release-qualification/0682889-source311-1gn95mji` | Absolute clean source checkout containing `src/` **and** `tests/` |
| `measure.py` | `/home/matthew/mlg-cli/.venv/bin/python` | Absolute application Python executable with compatible development dependencies |

For example, after supplying your own paths:

```bash
/usr/bin/python3 - "$repro_dir" /absolute/source /absolute/venv/bin/python <<'PY'
import hashlib
import sys
from pathlib import Path

directory, source, interpreter = map(Path, sys.argv[1:])
assert source.is_absolute() and (source / 'tests/cli/ui_scenarios.py').is_file()
assert interpreter.is_absolute() and interpreter.is_file()
replacements = {
    'run_measure.py': (
        '/home/matthew/.cache/henchman-release-qualification/0682889-source311-1gn95mji',
        str(source),
    ),
    'measure.py': ('/home/matthew/mlg-cli/.venv/bin/python', str(interpreter)),
}
for name, (old, new) in replacements.items():
    path = directory / name
    text = path.read_text()
    assert text.count(repr(old)) == 1
    path.write_text(text.replace(repr(old), repr(new)))
for name in ('measure.py', 'probe_app.py', 'run_measure.py'):
    print(name, hashlib.sha256((directory / name).read_bytes()).hexdigest())
PY
```

These replacements produce **different executed hashes**, even when measuring
the historical commit. Changing the source measures different production code;
neither case can be labeled the unchanged historical harness/cohort. Also review
the fixed `/usr/bin/python3` and `PATH` tool assumptions for the new environment.

The fixed scenario order is below. Each invocation owns a fresh Xvfb/VTE/app set
and runs 20 input plus 20 cancellation observations. Run only as a deliberate
local measurement, retain every scenario and supervise interruptions; this
publication did not execute these commands.

```bash
/usr/bin/python3 "$repro_dir/run_measure.py" cohort-0-80x24-40 80 24 40 \
  > "$repro_dir/cohort-0-80x24-40-supervisor.log" 2>&1
/usr/bin/python3 "$repro_dir/run_measure.py" cohort-1-80x24-1000 80 24 1000 \
  > "$repro_dir/cohort-1-80x24-1000-supervisor.log" 2>&1
/usr/bin/python3 "$repro_dir/run_measure.py" cohort-2-120x40-1000 120 40 1000 \
  > "$repro_dir/cohort-2-120x40-1000-supervisor.log" 2>&1
/usr/bin/python3 "$repro_dir/run_measure.py" cohort-3-120x40-40 120 40 40 \
  > "$repro_dir/cohort-3-120x40-40-supervisor.log" 2>&1
/usr/bin/python3 "$repro_dir/run_measure.py" cohort-4-160x50-40 160 50 40 \
  > "$repro_dir/cohort-4-160x50-40-supervisor.log" 2>&1
/usr/bin/python3 "$repro_dir/run_measure.py" cohort-5-160x50-1000 160 50 1000 \
  > "$repro_dir/cohort-5-160x50-1000-supervisor.log" 2>&1
```

Record each supervisor's exit code, elapsed time and host load separately; the
historical `cohort-results.json` aggregation is retained in the published JSON,
but its external aggregation driver was not one of the three frozen scripts.
A successful exit means measurement completion plus joined app cleanup, **not**
threshold success. Read `input_summary.criterion_passed` and
`cancel_summary.criterion_passed` in every `receipt.json`. Recompute p95 from
all 20 values using the 19th order statistic; retain failed/missing attempts
and investigate incomplete receipts instead of replacing them with best runs.
Final supervisor receipt publication follows Xvfb's `wait()`; retain both
receipt and supervisor/Xvfb logs as cleanup evidence.

The archive retains four pre-existing Ruff style findings (import ordering,
GI import placement, and a `try`/`except`/`pass` idiom) to preserve executed byte
identity. Publication checks compile syntax without executing the scripts,
compare exact hashes, parse finite JSON, reconcile all counts/percentiles and
verify calibration crops. This is not a new live-run or cleanup-fault
qualification. Actual process launch/X11/sampling overhead, software pixels,
shared-host load and small within-process samples remain measurement limits.
