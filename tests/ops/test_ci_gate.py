import json
import os
import subprocess
from pathlib import Path

import pytest
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


@pytest.mark.parametrize(
    "job_id, outcome",
    [
        ("lint", "failure"),
        ("lint", "cancelled"),
        ("lint", "skipped"),
        ("lint", "missing"),
        ("type-check", "failure"),
        ("type-check", "cancelled"),
        ("type-check", "skipped"),
        ("type-check", "missing"),
        ("test", "failure"),
        ("test", "cancelled"),
        ("test", "skipped"),
        ("test", "missing"),
        ("build-check", "failure"),
        ("build-check", "cancelled"),
        ("build-check", "skipped"),
        ("build-check", "missing"),
        ("native-smoke", "failure"),
        ("native-smoke", "cancelled"),
        ("native-smoke", "skipped"),
        ("native-smoke", "missing"),
    ],
)
def test_ci_gate_negative(tmp_path, job_id, outcome):
    workflow_path = Path(__file__).resolve().parents[2] / ".github/workflows/ci.yml"
    assert workflow_path.exists()

    with open(workflow_path) as f:
        config = yaml.safe_load(f)

    assert "aggregate-gate" in config["jobs"]
    aggregate_gate = config["jobs"]["aggregate-gate"]

    validate_step = None
    for step in aggregate_gate["steps"]:
        if step.get("name") == "Validate requirements":
            validate_step = step
            break

    assert validate_step is not None, "Validate requirements step not found"

    required_jobs = ["lint", "type-check", "test", "build-check", "native-smoke"]
    payload = {job_id: {"result": "success", "outputs": {}} for job_id in required_jobs}

    if outcome == "missing":
        del payload[job_id]
    elif outcome in ["failure", "cancelled", "skipped"]:
        payload[job_id] = {"result": outcome, "outputs": {}}

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

    assert (
        result.returncode != 0
    ), f"Expected non-zero exit code for {job_id} with outcome {outcome}, but got 0. Output: {result.stdout + result.stderr}"
