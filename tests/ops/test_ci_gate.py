import json
import os
import subprocess
from pathlib import Path

import yaml


def test_ci_gate_success(tmp_path):
    workflow_path = Path(__file__).resolve().parents[2] / ".github/workflows/ci.yml"
    assert workflow_path.exists()

    with open(workflow_path) as f:
        config = yaml.safe_load(f)

    assert "aggregate-gate" in config["jobs"]
    aggregate_gate = config["jobs"]["aggregate-gate"]

    assert aggregate_gate["if"] == "always()"
    assert "lint" in aggregate_gate["needs"]
    assert "type-check" in aggregate_gate["needs"]
    assert "test" in aggregate_gate["needs"]
    assert "build-check" in aggregate_gate["needs"]
    assert "native-smoke" in aggregate_gate["needs"]

    validate_step = None
    for step in aggregate_gate["steps"]:
        if step.get("name") == "Validate requirements":
            validate_step = step
            break

    assert validate_step is not None, "Validate requirements step not found"

    assert validate_step["env"]["NEEDS_JSON"] == "${{ toJSON(needs) }}"

    required_jobs = ["lint", "type-check", "test", "build-check", "native-smoke"]
    payload = {job_id: {"result": "success", "outputs": {}} for job_id in required_jobs}

    script = validate_step["run"]

    env = {**os.environ, "NEEDS_JSON": json.dumps(payload)}

    result = subprocess.run(
        ["bash", "--noprofile", "--norc", "-e", "-o", "pipefail", "-c", script],
        env=env,
        cwd=tmp_path,
        capture_output=True,
        text=True,
        timeout=10,
    )

    assert result.returncode == 0, result.stdout + result.stderr
