"""Offline wheel lifecycle checks use real builds and isolated installations."""

import shutil
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

import pytest

from henchman.tools.subprocess_utils import run_bounded_subprocess

GOOD_LIBRARY = """from collections.abc import Iterable

import label_rules


def unique_labels(values: Iterable[str]) -> list[str]:
    result: list[str] = []
    for value in values:
        normalized = label_rules.normalize_label(value)
        if normalized and normalized not in result:
            result.append(normalized)
    return result
"""
GOOD_CLI = """import argparse
import json
from importlib.resources import files

from release_labels import unique_labels


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("labels", nargs="*")
    args = parser.parse_args()
    key = json.loads(files("release_labels").joinpath("data/defaults.json").read_text())["key"]
    print(json.dumps({key: unique_labels(args.labels)}, ensure_ascii=False))
    return 0
"""


async def completed_workspace(workspace: Path):
    from evals.package_oracle import prepare_package_workspace

    baseline = await prepare_package_workspace(workspace)
    (workspace / "src/release_labels/__init__.py").write_text(GOOD_LIBRARY)
    (workspace / "src/release_labels/cli.py").write_text(GOOD_CLI)
    await build_model_wheel(workspace)
    return baseline


async def build_model_wheel(workspace: Path) -> None:
    uv = shutil.which("uv")
    assert uv, "These offline integration contracts require uv and its cached hatchling backend"
    dist = workspace / "dist"
    shutil.rmtree(dist, ignore_errors=True)
    result = await run_bounded_subprocess(
        [
            uv,
            "--no-config",
            "--offline",
            "--no-python-downloads",
            "build",
            "--wheel",
            "--out-dir",
            str(dist),
        ],
        cwd=workspace,
        timeout=60,
        max_output_bytes=8192,
    )
    assert result.returncode == 0, (result.stdout + result.stderr).decode()


@pytest.mark.asyncio
async def test_real_offline_build_install_and_cli_pass_outside_checkout(tmp_path, monkeypatch):
    from evals.package_oracle import verify_package_artifacts

    baseline = await completed_workspace(tmp_path)
    contamination = tmp_path / "contamination"
    contamination.mkdir()
    (contamination / "release_labels.py").write_text("raise RuntimeError('checkout contamination')")
    monkeypatch.setenv("PYTHONPATH", str(contamination))
    monkeypatch.setenv("PYTHONOPTIMIZE", "2")
    report = await verify_package_artifacts(tmp_path, baseline)
    assert report["success"], report
    assert report["task_verified"] is False
    assert all(check["success"] for check in report["checks"].values()), report
    assert report["artifacts"]["executed_tests"] == 5
    assert report["artifacts"]["model_wheel_sha256"]
    assert report["artifacts"]["fresh_wheel_sha256"]


@pytest.mark.asyncio
@pytest.mark.parametrize("defect", ["fake", "data", "dependency", "entrypoint"])
async def test_rejects_invalid_or_incomplete_submitted_wheel(tmp_path, defect):
    from evals.package_oracle import verify_package_artifacts

    baseline = await completed_workspace(tmp_path)
    wheel = next((tmp_path / "dist").glob("*.whl"))
    if defect == "fake":
        wheel.write_bytes(b"not a wheel")
    else:
        with ZipFile(wheel) as archive:
            entries = {name: archive.read(name) for name in archive.namelist()}
        if defect == "data":
            entries.pop("release_labels/data/defaults.json")
        elif defect == "entrypoint":
            entries = {
                name: data
                for name, data in entries.items()
                if not name.endswith("entry_points.txt")
            }
        else:
            for name in entries:
                if name.endswith("METADATA"):
                    entries[name] = b"\n".join(
                        line
                        for line in entries[name].split(b"\n")
                        if not line.startswith(b"Requires-Dist:")
                    )
        with ZipFile(wheel, "w", ZIP_DEFLATED) as archive:
            for name, data in entries.items():
                archive.writestr(name, data)
    report = await verify_package_artifacts(tmp_path, baseline)
    assert not report["success"], report
    assert not report["checks"]["submitted_wheel"]["success"], report


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "path",
    [
        "pyproject.toml",
        "tests/test_installed.py",
        ".github/workflows/ci.yml",
        "src/release_labels/data/defaults.json",
    ],
)
async def test_rejects_weakened_protected_contract(tmp_path, path):
    from evals.package_oracle import prepare_package_workspace, verify_package_artifacts

    baseline = await prepare_package_workspace(tmp_path)
    (tmp_path / path).write_text("weakened")
    report = await verify_package_artifacts(tmp_path, baseline)
    assert not report["success"], report
    assert not report["checks"]["protected_files"]["success"], report


@pytest.mark.asyncio
@pytest.mark.parametrize("defect", ["early_exit", "copied_helper", "stale_wheel"])
async def test_rejects_false_behavior_receipts_and_source_wheel_mismatch(tmp_path, defect):
    from evals.package_oracle import verify_package_artifacts

    baseline = await completed_workspace(tmp_path)
    source = tmp_path / "src/release_labels/__init__.py"
    if defect == "early_exit":
        source.write_text("import os\nos._exit(0)\n" + GOOD_LIBRARY)
    elif defect == "copied_helper":
        source.write_text(
            GOOD_LIBRARY.replace(
                "label_rules.normalize_label(value)", '"-".join(value.casefold().split())'
            )
        )
    else:
        source.write_text(GOOD_LIBRARY + "\nFINAL_SOURCE_CHANGE = True\n")
    if defect != "stale_wheel":
        await build_model_wheel(tmp_path)
    report = await verify_package_artifacts(tmp_path, baseline)
    assert not report["success"], report
    check = "wheel_matches_source" if defect == "stale_wheel" else "installed_tests"
    assert not report["checks"][check]["success"], report


@pytest.mark.asyncio
@pytest.mark.parametrize("defect", ["missing", "symlink", "oversize"])
async def test_protected_artifact_reads_fail_closed(tmp_path, defect):
    from evals.package_oracle import (
        MAX_FILE_BYTES,
        prepare_package_workspace,
        verify_package_artifacts,
    )

    baseline = await prepare_package_workspace(tmp_path)
    protected = tmp_path / "pyproject.toml"
    if defect == "missing":
        protected.unlink()
    elif defect == "oversize":
        protected.write_bytes(b"x" * (MAX_FILE_BYTES + 1))
    else:
        external = tmp_path.parent / (tmp_path.name + "-config.toml")
        external.write_bytes(protected.read_bytes())
        protected.unlink()
        try:
            protected.symlink_to(external)
        except OSError as exc:
            pytest.skip(f"Symlink creation unavailable: {exc}")
    report = await verify_package_artifacts(tmp_path, baseline)
    assert not report["checks"]["protected_files"]["success"], report
    assert not report["success"], report


@pytest.mark.asyncio
async def test_source_change_during_verification_fails_stability(tmp_path, monkeypatch):
    import evals.package_oracle as oracle

    baseline = await completed_workspace(tmp_path)
    real_build = oracle._build

    async def build_then_change(project, destination):
        result = await real_build(project, destination)
        if destination.name == "fresh-dist":
            (tmp_path / "src/release_labels/cli.py").write_text(GOOD_CLI + "\nLATE_CHANGE = True\n")
        return result

    monkeypatch.setattr(oracle, "_build", build_then_change)
    report = await oracle.verify_package_artifacts(tmp_path, baseline)
    assert not report["success"], report
    assert not report["checks"]["artifacts_stable"]["success"], report


@pytest.mark.asyncio
async def test_missing_uv_fails_explicitly_without_download(tmp_path, monkeypatch):
    import evals.package_oracle as oracle

    monkeypatch.setattr(shutil, "which", lambda _: None)
    with pytest.raises(ValueError, match="requires uv"):
        await oracle.prepare_package_workspace(tmp_path)


@pytest.mark.asyncio
async def test_empty_backend_cache_fails_offline(tmp_path, monkeypatch):
    from evals.package_oracle import prepare_package_workspace

    monkeypatch.setenv("UV_CACHE_DIR", str(tmp_path / "empty-uv-cache"))
    with pytest.raises(ValueError, match="Command exited"):
        await prepare_package_workspace(tmp_path)


@pytest.mark.asyncio
async def test_pip_configuration_cannot_redirect_isolated_install(tmp_path, monkeypatch):
    from evals.package_oracle import verify_package_artifacts

    baseline = await completed_workspace(tmp_path)
    redirected = tmp_path / "unexpected-install"
    config = tmp_path / "pip.ini"
    config.write_text(f"[global]\ntarget = {redirected}\n")
    monkeypatch.setenv("PIP_CONFIG_FILE", str(config))
    monkeypatch.setenv("PIP_TARGET", str(redirected))
    report = await verify_package_artifacts(tmp_path, baseline)
    assert not redirected.exists(), "Oracle installed outside its private environment"
    assert report["success"], report


@pytest.mark.asyncio
async def test_submitted_wheel_filename_must_be_installable(tmp_path):
    from evals.package_oracle import verify_package_artifacts

    baseline = await completed_workspace(tmp_path)
    wheel = next((tmp_path / "dist").glob("*.whl"))
    wheel.rename(wheel.with_name("fake.whl"))
    report = await verify_package_artifacts(tmp_path, baseline)
    assert not report["success"], report
    assert not report["checks"]["submitted_wheel"]["success"], report


@pytest.mark.asyncio
async def test_cli_cannot_duplicate_library_or_hardcode_packaged_key(tmp_path):
    from evals.package_oracle import verify_package_artifacts

    baseline = await completed_workspace(tmp_path)
    (tmp_path / "src/release_labels/cli.py").write_text("""import argparse
import json


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("labels", nargs="*")
    args = parser.parse_args()
    labels = list(dict.fromkeys("-".join(value.casefold().split()) for value in args.labels if value.strip()))
    print(json.dumps({"labels": labels}))
    return 0
""")
    await build_model_wheel(tmp_path)
    report = await verify_package_artifacts(tmp_path, baseline)
    assert not report["success"], report
    assert not report["checks"]["installed_tests"]["success"], report


@pytest.mark.asyncio
async def test_dependency_reuse_accepts_direct_function_import(tmp_path):
    from evals.package_oracle import verify_package_artifacts

    baseline = await completed_workspace(tmp_path)
    direct_import = GOOD_LIBRARY.replace(
        "import label_rules", "from label_rules import normalize_label"
    )
    direct_import = direct_import.replace(
        "label_rules.normalize_label(value)", "normalize_label(value)"
    )
    (tmp_path / "src/release_labels/__init__.py").write_text(direct_import)
    await build_model_wheel(tmp_path)
    report = await verify_package_artifacts(tmp_path, baseline)
    assert report["success"], report


@pytest.mark.asyncio
async def test_cli_accepts_resource_key_cached_at_library_import(tmp_path):
    from evals.package_oracle import verify_package_artifacts

    baseline = await completed_workspace(tmp_path)
    cached_library = (
        GOOD_LIBRARY
        + """\nimport json
from importlib.resources import files

DEFAULT_KEY = json.loads(files("release_labels").joinpath("data/defaults.json").read_text())["key"]
"""
    )
    cached_cli = GOOD_CLI.replace(
        "from release_labels import unique_labels",
        "from release_labels import DEFAULT_KEY, unique_labels",
    ).replace(
        'key = json.loads(files("release_labels").joinpath("data/defaults.json").read_text())["key"]',
        "key = DEFAULT_KEY",
    )
    (tmp_path / "src/release_labels/__init__.py").write_text(cached_library)
    (tmp_path / "src/release_labels/cli.py").write_text(cached_cli)
    await build_model_wheel(tmp_path)
    report = await verify_package_artifacts(tmp_path, baseline)
    assert report["success"], report
