"""Offline package lifecycle evidence; neither a sandbox nor hosted CI verification."""

from __future__ import annotations

import base64
import configparser
import csv
import hashlib
import io
import json
import os
import shutil
import stat
import sys
import tempfile
from dataclasses import dataclass
from email.parser import BytesParser
from pathlib import Path, PurePosixPath
from typing import Any
from zipfile import ZipFile

from henchman.tools.security import sanitize_error_message
from henchman.tools.subprocess_utils import BoundedProcessResult, run_bounded_subprocess

MAX_FILE_BYTES = 1_048_576
MAX_WHEEL_BYTES = 2_097_152
EDITABLE_FILES = ("src/release_labels/__init__.py", "src/release_labels/cli.py")
DEPENDENCY_SOURCE = '''def normalize_label(value: str) -> str:
    """Canonicalize whitespace and Unicode case, preserving input values."""
    return "-".join(value.casefold().split())
'''
PYPROJECT = """[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "release-labels"
version = "1.0.0"
requires-python = ">=3.11"
dependencies = ["label-rules==1.0.0"]

[project.scripts]
release-labels = "release_labels.cli:main"

[tool.hatch.build.targets.wheel]
packages = ["src/release_labels"]
"""
DEPENDENCY_PROJECT = """[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "label-rules"
version = "1.0.0"
requires-python = ">=3.11"

[tool.hatch.build.targets.wheel]
packages = ["src/label_rules"]
"""
INSTALLED_TESTS = """import importlib
import io
import json
import sys
import unittest
from contextlib import redirect_stdout
from importlib.resources import files
from pathlib import Path
from unittest.mock import patch

import label_rules
import release_labels
from release_labels import unique_labels


class PackageTests(unittest.TestCase):
    def test_unicode_order(self):
        self.assertEqual(unique_labels([" Red Fox ", "RED FOX", "Straße", "STRASSE", ""]),
                         ["red-fox", "strasse"])

    def test_empty(self):
        self.assertEqual(unique_labels([]), [])

    def test_inputs_unchanged(self):
        inputs = [" B ", "A", "b"]
        self.assertEqual(unique_labels(inputs), ["b", "a"])
        self.assertEqual(inputs, [" B ", "A", "b"])

    def test_dependency_used_for_every_input(self):
        try:
            with patch.object(label_rules, "normalize_label", side_effect=["one", "two", "one", ""]) as helper:
                importlib.reload(release_labels)
                self.assertEqual(release_labels.unique_labels(["x", "y", "z", "w"]), ["one", "two"])
                self.assertEqual([call.args for call in helper.call_args_list], [("x",), ("y",), ("z",), ("w",)])
        finally:
            importlib.reload(release_labels)

    def test_packaged_data(self):
        resource = Path(str(files("release_labels").joinpath("data/defaults.json")))
        data = resource.read_text(encoding="utf-8")
        self.assertEqual(json.loads(data), {"key": "labels"})
        try:
            resource.write_text('{"key": "resource-sentinel"}', encoding="utf-8")
            importlib.reload(release_labels)
            sys.modules.pop("release_labels.cli", None)
            output = io.StringIO()
            with patch.object(release_labels, "unique_labels", return_value=["helper-sentinel"]) as helper:
                cli = importlib.import_module("release_labels.cli")
                with patch.object(sys, "argv", ["release-labels", "input"]), redirect_stdout(output):
                    self.assertIn(cli.main(), (None, 0))
                helper.assert_called_once_with(["input"])
            self.assertEqual(json.loads(output.getvalue()), {"resource-sentinel": ["helper-sentinel"]})
        finally:
            resource.write_text(data, encoding="utf-8")
            importlib.reload(release_labels)
            if "release_labels.cli" in sys.modules:
                importlib.reload(sys.modules["release_labels.cli"])
"""
CI_CONFIG = """name: package-checks
on: [push, pull_request]
jobs:
  package:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v6
      - run: uv build --offline --wheel --out-dir dist
      - run: python -m venv .package-check
      - run: .package-check/bin/python -m pip install --no-index --find-links .wheelhouse dist/*.whl
      - run: .package-check/bin/python -m unittest discover -s tests
"""
FIXTURES = {
    "pyproject.toml": PYPROJECT,
    EDITABLE_FILES[
        0
    ]: 'def unique_labels(values: list[str]) -> list[str]:\n    raise NotImplementedError("Reuse label_rules.normalize_label for every input")\n',
    EDITABLE_FILES[
        1
    ]: 'def main() -> int:\n    raise NotImplementedError("Print JSON using the packaged defaults and unique_labels")\n',
    "src/release_labels/data/defaults.json": '{"key": "labels"}\n',
    "tests/test_installed.py": INSTALLED_TESTS,
    "reference/label_rules.py": DEPENDENCY_SOURCE,
    ".github/workflows/ci.yml": CI_CONFIG,
}
PACKAGE_TASK = """Complete this offline Python package task with the production team.
Inspect the existing package, reference/label_rules.py (the exact source of the
pinned local dependency), tests, packaging configuration, and CI configuration
before implementation. Implement only
src/release_labels/__init__.py and src/release_labels/cli.py.
unique_labels(values) must call label_rules.normalize_label for EVERY input, return
nonempty normalized labels once each in first-seen order, preserve the input, and
support Unicode casefolding. Do not copy the dependency's implementation.
The installed release-labels console command accepts positional labels and prints
one JSON object, using the key from packaged data/defaults.json and unique_labels
for its value. No arguments prints {"labels": []}; unsupported options exit 2.
Keep pyproject.toml, data/defaults.json, tests/test_installed.py, reference/label_rules.py,
CI configuration, and the supplied .wheelhouse dependency wheel unchanged. Do not install into the
agent's active environment. Any agent-side installation must use a fresh virtual
environment without system site packages and --no-index --find-links .wheelhouse.
Build exactly one final wheel into dist with uv build --offline --wheel --out-dir dist.
Use argv-only subprocess execution with finite timeouts for build/install/checks;
python_exec can launch subprocesses with argument lists. Never use downloads,
network package indexes, publishing, or deployment. Missing offline tools or
cached build dependencies must be reported as failures.
Deliver the final implementation and wheel. The independent evaluator will rebuild
from source, install the submitted wheel in its own fresh environment, run all
five protected unittest tests, and exercise the installed console command outside
the checkout. You may run your own isolated checks; report precisely which ones
you actually ran. Have another specialist inspect both final implementation files.
The evaluator independently validates packaging. Inspect the immutable CI YAML;
the evaluator runs fixed local
build/install/test equivalents. Do not claim hosted CI ran or count evaluator
checks as agent actions. Report actual commands, outcomes, and unresolved failures.
"""
PROTECTED_FILES = tuple(name for name in FIXTURES if name not in EDITABLE_FILES)
SPEC_DIGEST = hashlib.sha256(
    json.dumps(
        {
            "fixtures": FIXTURES,
            "dependency_project": DEPENDENCY_PROJECT,
            "dependency_source": DEPENDENCY_SOURCE,
            "task": PACKAGE_TASK,
        },
        sort_keys=True,
    ).encode()
).hexdigest()


@dataclass(frozen=True)
class PackageBaseline:
    """Trusted initial fingerprints; no temporary resource lifetime is retained."""

    initial_hashes: tuple[tuple[str, str], ...]
    protected_hashes: tuple[tuple[str, str], ...]
    dependency_wheel: str


def _read(root: Path, relative: str, limit: int = MAX_FILE_BYTES) -> bytes:
    path = root
    for part in PurePosixPath(relative).parts:
        if part in {"..", "/"}:
            raise ValueError("Artifact path escapes workspace")
        path = path / part
        if path.is_symlink():
            raise ValueError(f"Symlinked artifact: {relative}")
    if not path.is_file():
        raise ValueError(f"Missing artifact: {relative}")
    with path.open("rb") as stream:
        data = stream.read(limit + 1)
    if len(data) > limit:
        raise ValueError(f"Oversized artifact: {relative}")
    return data


def _digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _snapshot(root: Path, paths: tuple[str, ...]) -> dict[str, str]:
    return {name: _digest(_read(root, name)) for name in paths}


async def _run(command: list[str], cwd: Path, *, timeout: int = 60) -> BoundedProcessResult:
    # The shared runner has no environment override. Clean only the child before
    # exec; pip --isolated still honors an inherited PIP_CONFIG_FILE otherwise.
    result = await run_bounded_subprocess(
        [sys.executable, "-I", "-c", _CLEAN_EXEC, *command],
        cwd=cwd,
        timeout=timeout,
        max_output_bytes=8192,
    )
    if result.returncode != 0 or result.stdout_truncated or result.stderr_truncated:
        output = (result.stdout + result.stderr).decode("utf-8", errors="replace")
        raise ValueError(f"Command exited {result.returncode} or exceeded output bound: {output}")
    return result


def _one_wheel(directory: Path) -> Path:
    if directory.is_symlink() or not directory.is_dir():
        raise ValueError("Missing or symlinked wheel directory")
    wheels = []
    with os.scandir(directory) as entries:
        for index, entry in enumerate(entries):
            if index >= 32:
                raise ValueError("Too many wheel directory entries")
            if entry.name.endswith(".whl"):
                wheels.append(Path(entry.path))
    if len(wheels) != 1:
        raise ValueError(f"Expected exactly one wheel, found {len(wheels)}")
    _read(directory, wheels[0].name, MAX_WHEEL_BYTES)
    return wheels[0]


async def _build(project: Path, destination: Path) -> Path:
    uv = shutil.which("uv")
    if uv is None:
        raise ValueError("Offline build requires uv and its cached hatchling backend")
    await _run(
        [
            uv,
            "--no-config",
            "--offline",
            "--no-python-downloads",
            "build",
            "--wheel",
            "--out-dir",
            str(destination),
        ],
        project,
    )
    return _one_wheel(destination)


async def _dependency(root: Path) -> Path:
    project = root / "dependency-source"
    (project / "src/label_rules").mkdir(parents=True)
    (project / "pyproject.toml").write_text(DEPENDENCY_PROJECT, encoding="utf-8")
    (project / "src/label_rules/__init__.py").write_text(DEPENDENCY_SOURCE, encoding="utf-8")
    return await _build(project, root / "wheelhouse")


async def prepare_package_workspace(workspace: Path) -> PackageBaseline:
    """Write the fixed task and build its pinned dependency without network access."""
    if workspace.is_symlink():
        raise ValueError("Workspace must not be a symlink")
    workspace.mkdir(parents=True, exist_ok=True)
    for name, contents in FIXTURES.items():
        target = workspace / name
        cursor = target
        while cursor != workspace:
            if cursor.is_symlink():
                raise ValueError(f"Symlinked fixture destination: {name}")
            cursor = cursor.parent
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(contents, encoding="utf-8")
    with tempfile.TemporaryDirectory(prefix="henchman-package-dependency-") as temporary:
        wheel = await _dependency(Path(temporary))
        relative = f".wheelhouse/{wheel.name}"
        destination = workspace / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        if destination.parent.is_symlink() or destination.is_symlink():
            raise ValueError("Symlinked dependency wheelhouse")
        shutil.copyfile(wheel, destination)
    paths = (*FIXTURES, relative)
    initial = tuple(_snapshot(workspace, paths).items())
    protected = tuple((name, digest) for name, digest in initial if name not in EDITABLE_FILES)
    return PackageBaseline(initial, protected, relative)


def _wheel_payload(wheel: Path) -> dict[str, bytes]:
    if wheel.name != "release_labels-1.0.0-py3-none-any.whl":
        raise ValueError("Submitted wheel must have its canonical installable filename")
    raw = _read(wheel.parent, wheel.name, MAX_WHEEL_BYTES)
    with ZipFile(io.BytesIO(raw)) as archive:
        members = archive.infolist()
        if not 1 <= len(members) <= 32 or sum(item.file_size for item in members) > MAX_WHEEL_BYTES:
            raise ValueError("Wheel archive exceeds member or size bound")
        payload: dict[str, bytes] = {}
        for item in members:
            name = item.filename
            path = PurePosixPath(name)
            if (
                name in payload
                or path.is_absolute()
                or ".." in path.parts
                or "\\" in name
                or stat.S_ISLNK(item.external_attr >> 16)
                or item.is_dir()
                or item.file_size > MAX_FILE_BYTES
            ):
                raise ValueError(f"Invalid wheel member: {name}")
            payload[name] = archive.read(item)
    prefix = "release_labels-1.0.0.dist-info/"
    expected = {
        "release_labels/__init__.py",
        "release_labels/cli.py",
        "release_labels/data/defaults.json",
        *(prefix + name for name in ("METADATA", "WHEEL", "entry_points.txt", "RECORD")),
    }
    if payload.keys() != expected:
        raise ValueError("Wheel has missing or unexpected package/data/metadata members")
    metadata = BytesParser().parsebytes(payload[prefix + "METADATA"])
    if (
        metadata["Name"] != "release-labels"
        or metadata["Version"] != "1.0.0"
        or metadata.get_all("Requires-Dist") != ["label-rules==1.0.0"]
        or metadata["Requires-Python"] != ">=3.11"
    ):
        raise ValueError("Wheel package identity or pinned dependency metadata differs")
    wheel_metadata = BytesParser().parsebytes(payload[prefix + "WHEEL"])
    if wheel_metadata["Root-Is-Purelib"] != "true" or wheel_metadata["Tag"] != "py3-none-any":
        raise ValueError("Expected a portable pure Python wheel")
    entrypoints = configparser.ConfigParser()
    entrypoints.read_string(payload[prefix + "entry_points.txt"].decode())
    if dict(entrypoints["console_scripts"]) != {"release-labels": "release_labels.cli:main"}:
        raise ValueError("Missing or incorrect installed CLI entrypoint")
    if (
        payload["release_labels/data/defaults.json"]
        != FIXTURES["src/release_labels/data/defaults.json"].encode()
    ):
        raise ValueError("Packaged data differs")
    rows = list(csv.reader(io.StringIO(payload[prefix + "RECORD"].decode())))
    if len(rows) != len(payload) or {row[0] for row in rows} != payload.keys():
        raise ValueError("Wheel RECORD does not cover exactly its payload")
    for row in rows:
        if len(row) != 3:
            raise ValueError("Invalid wheel RECORD row")
        name, digest, size = row
        if name == prefix + "RECORD":
            if digest or size:
                raise ValueError("Invalid self-referential RECORD")
        else:
            expected_hash = (
                base64.urlsafe_b64encode(hashlib.sha256(payload[name]).digest())
                .rstrip(b"=")
                .decode()
            )
            if digest != f"sha256={expected_hash}" or size != str(len(payload[name])):
                raise ValueError("Wheel RECORD hash or size mismatch")
    return {name: value for name, value in payload.items() if not name.endswith("/RECORD")}


_TEST_BOOTSTRAP = """import importlib.metadata, json, pathlib, sys, unittest
receipt = pathlib.Path(sys.argv[2])
import release_labels, label_rules
for name, module in [("release-labels", release_labels), ("label-rules", label_rules)]:
    distribution = importlib.metadata.distribution(name)
    actual = pathlib.Path(module.__file__).resolve()
    expected = distribution.locate_file(name.replace("-", "_") + "/__init__.py").resolve()
    if actual != expected or not actual.is_relative_to(pathlib.Path(sys.prefix).resolve()):
        raise RuntimeError("Imported source outside isolated installation")
    if distribution.version != "1.0.0":
        raise RuntimeError("Wrong installed distribution version")
namespace = {"__name__": "independent_package_tests"}
exec(compile(pathlib.Path(sys.argv[1]).read_text(), sys.argv[1], "exec"), namespace)
suite = unittest.defaultTestLoader.loadTestsFromTestCase(namespace["PackageTests"])
result = unittest.TextTestRunner().run(suite)
if result.testsRun != 5 or not result.wasSuccessful() or result.skipped:
    raise RuntimeError("Not all five independent tests executed and passed")
receipt.write_text(json.dumps({"executed_tests": result.testsRun}), encoding="utf-8")
"""
_CLEAN_EXEC = """import os, sys
for name in ("PYTHONPATH", "PYTHONHOME", "PYTHONOPTIMIZE"):
    os.environ.pop(name, None)
for name in tuple(os.environ):
    if name.startswith("PIP_"):
        os.environ.pop(name, None)
os.environ["PIP_CONFIG_FILE"] = os.devnull
os.execv(sys.argv[1], sys.argv[1:])
"""


async def verify_package_artifacts(workspace: Path, baseline: PackageBaseline) -> dict[str, Any]:
    """Build, validate and install offline; return scoped evidence even when a check fails."""
    names = (
        "protected_files",
        "ci_config",
        "submitted_wheel",
        "fresh_build",
        "wheel_matches_source",
        "isolated_install",
        "installed_tests",
        "installed_cli",
        "artifacts_stable",
    )
    report: dict[str, Any] = {
        "success": False,
        "task_verified": False,
        "checks": {name: {"success": False, "error": "Not run"} for name in names},
        "artifacts": {},
        "scope": "Offline local build/install/tests and fixed CI equivalents; no hosted CI run",
    }
    stage = "protected_files"
    initial: dict[str, str] | None = None
    submitted: Path | None = None
    submitted_hash: str | None = None
    try:
        if workspace.is_symlink():
            raise ValueError("Symlinked workspace")
        initial = _snapshot(workspace, tuple(dict(baseline.initial_hashes)))
        if any(initial.get(name) != digest for name, digest in baseline.protected_hashes):
            raise ValueError("Protected fixture changed")
        report["checks"][stage] = {"success": True, "error": None}
        stage = "ci_config"
        import yaml

        ci = yaml.safe_load(_read(workspace, ".github/workflows/ci.yml"))
        if ci != yaml.safe_load(CI_CONFIG):
            raise ValueError("CI configuration differs from fixed local contract")
        report["checks"][stage] = {"success": True, "error": None}
        stage = "submitted_wheel"
        submitted = _one_wheel(workspace / "dist")
        submitted_hash = _digest(_read(submitted.parent, submitted.name, MAX_WHEEL_BYTES))
        submitted_payload = _wheel_payload(submitted)
        report["artifacts"]["model_wheel_sha256"] = submitted_hash
        report["checks"][stage] = {"success": True, "error": None}
        with tempfile.TemporaryDirectory(prefix="henchman-package-oracle-") as temporary:
            outside = Path(temporary)
            source = outside / "source"
            # Rebuild only the known final source and protected packaging configuration.
            # Agent-created build hooks or checkout injection files are not oracle inputs.
            for name in FIXTURES:
                target = source / name
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(_read(workspace, name))
            stage = "fresh_build"
            fresh = await _build(source, outside / "fresh-dist")
            fresh_payload = _wheel_payload(fresh)
            report["artifacts"]["fresh_wheel_sha256"] = _digest(
                _read(fresh.parent, fresh.name, MAX_WHEEL_BYTES)
            )
            report["checks"][stage] = {"success": True, "error": None}
            stage = "wheel_matches_source"
            if submitted_payload != fresh_payload:
                raise ValueError(
                    "Submitted wheel payload differs from independently rebuilt final source"
                )
            report["checks"][stage] = {"success": True, "error": None}
            stage = "isolated_install"
            dependency = await _dependency(outside)
            submitted_copy = outside / submitted.name
            submitted_bytes = _read(submitted.parent, submitted.name, MAX_WHEEL_BYTES)
            if _digest(submitted_bytes) != submitted_hash:
                raise ValueError("Submitted wheel changed before installation")
            submitted_copy.write_bytes(submitted_bytes)
            environment = outside / "venv"
            await _run(
                [sys.executable, "-I", "-m", "venv", "--without-pip", str(environment)], outside
            )
            python = environment / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
            await _run([str(python), "-I", "-m", "ensurepip", "--default-pip"], outside)
            await _run(
                [
                    str(python),
                    "-I",
                    "-m",
                    "pip",
                    "--isolated",
                    "install",
                    "--no-index",
                    "--no-cache-dir",
                    "--no-compile",
                    "--find-links",
                    str(dependency.parent),
                    str(submitted_copy),
                ],
                outside,
            )
            await _run([str(python), "-I", "-m", "pip", "--isolated", "check"], outside)
            report["checks"][stage] = {"success": True, "error": None}
            stage = "installed_tests"
            tests = outside / "test_installed.py"
            tests.write_text(INSTALLED_TESTS, encoding="utf-8")
            receipt = outside / "tests-completed.json"
            await _run(
                [str(python), "-I", "-B", "-c", _TEST_BOOTSTRAP, str(tests), str(receipt)],
                outside,
                timeout=15,
            )
            if not receipt.is_file() or json.loads(_read(outside, receipt.name)) != {
                "executed_tests": 5
            }:
                raise ValueError("Independent tests exited without their completion receipt")
            report["artifacts"]["executed_tests"] = 5
            report["checks"][stage] = {"success": True, "error": None}
            stage = "installed_cli"
            executable = environment / (
                "Scripts/release-labels.exe" if os.name == "nt" else "bin/release-labels"
            )
            for args, expected in [
                ([], {"labels": []}),
                (
                    [" Red Fox ", "RED FOX", "Straße", "STRASSE", ""],
                    {"labels": ["red-fox", "strasse"]},
                ),
            ]:
                result = await _run(
                    [str(python), "-I", "-c", _CLEAN_EXEC, str(executable), *args],
                    outside,
                    timeout=15,
                )
                if json.loads(result.stdout) != expected:
                    raise ValueError("Installed CLI returned incorrect JSON")
            invalid = await run_bounded_subprocess(
                [str(python), "-I", "-c", _CLEAN_EXEC, str(executable), "--invalid"],
                cwd=outside,
                timeout=15,
                max_output_bytes=8192,
            )
            if invalid.returncode != 2 or invalid.stdout_truncated or invalid.stderr_truncated:
                raise ValueError("Installed CLI must reject unsupported options with exit 2")
            report["checks"][stage] = {"success": True, "error": None}
    except Exception as exc:
        report["checks"][stage] = {
            "success": False,
            "error": sanitize_error_message(f"{type(exc).__name__}: {exc}")[:8192],
        }
    finally:
        try:
            if initial is None or _snapshot(workspace, tuple(initial)) != initial:
                raise ValueError(
                    "Tracked source or fixture changed during independent verification"
                )
            if (
                submitted is not None
                and submitted_hash is not None
                and _digest(_read(submitted.parent, submitted.name, MAX_WHEEL_BYTES))
                != submitted_hash
            ):
                raise ValueError("Submitted wheel changed during independent verification")
            report["checks"]["artifacts_stable"] = {"success": True, "error": None}
        except Exception as exc:
            report["checks"]["artifacts_stable"] = {"success": False, "error": str(exc)[:8192]}
    report["success"] = all(check["success"] for check in report["checks"].values())
    return report
