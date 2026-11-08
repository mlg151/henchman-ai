"""Validate milestone releases and publish using the repository's INI secret."""

import ast
import configparser
import contextlib
import email
import hashlib
import json
import os
import re
import runpy
import signal
import subprocess
import sys
import tarfile
import tempfile
import time
import tomllib
import zipfile
from pathlib import Path
from typing import Any, BinaryIO


def parse_pypi_token(fragment: str) -> str:
    """Extract a token without including credential contents in errors."""
    config = configparser.ConfigParser(interpolation=None)
    try:
        config.read_string(fragment)
        username = config.get("pypi", "username", fallback="__token__").strip()
        token = config.get("pypi", "password").strip()
    except configparser.Error:
        raise ValueError("PYPI must contain a [pypi] configuration with a password") from None
    if username not in {"__token__", "**token**"} or not re.fullmatch(r"pypi-\S+", token):
        raise ValueError("PYPI must contain token authentication credentials")
    return token


def validate_release(root: Path, milestone: str) -> str:
    """Require the milestone and both committed version declarations to agree."""
    if not re.fullmatch(r"v?\d+\.\d+\.\d+", milestone):
        raise ValueError("Release milestone must be a version such as v0.4.1")
    version = milestone.removeprefix("v")
    metadata = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
    runtime = runpy.run_path(str(root / "src/henchman/version.py"))
    if metadata["project"]["version"] != version or runtime["VERSION"] != version:
        raise ValueError("Package and runtime version must match the release milestone")
    return version


def prepare_provenance(root: Path, version: str, commit: str, pr: str) -> None:
    """Bind package contents to one tested commit before hash-aware upload."""
    if not re.fullmatch(r"[0-9a-f]{40}", commit) or not pr.isdecimal():
        raise ValueError("Release provenance requires a commit SHA and PR number")
    provenance = {"commit": commit, "milestone": f"v{version}", "pr": int(pr)}
    (root / "src/henchman/_release.json").write_text(
        json.dumps(provenance, sort_keys=True) + "\n", encoding="utf-8"
    )


def _validate_contents(
    metadata: bytes, runtime: bytes, provenance: bytes, version: str, commit: str
) -> None:
    """Inspect distribution data without importing or extracting its code."""
    message = email.message_from_bytes(metadata)
    if message["Name"] != "henchman-ai" or message["Version"] != version:
        raise ValueError("Distribution metadata does not match the release version")
    values: dict[str, object] = {}
    for node in ast.parse(runtime).body:
        if isinstance(node, ast.Assign) and isinstance(node.value, (ast.Constant, ast.Tuple)):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id in {"VERSION", "VERSION_TUPLE"}:
                    values[target.id] = ast.literal_eval(node.value)
    runtime_version = values.get("VERSION")
    version_tuple = values.get("VERSION_TUPLE")
    if isinstance(version_tuple, tuple):
        runtime_version = ".".join(map(str, version_tuple))
    if runtime_version != version:
        raise ValueError("Distribution runtime version does not match the release version")
    record = json.loads(provenance)
    if record.get("commit") != commit or record.get("milestone") != f"v{version}":
        raise ValueError("Distribution provenance does not match the tested commit")


def validate_distributions(dist: Path, version: str, commit: str) -> list[Path]:
    """Require both archives to contain the correct metadata and provenance."""
    files = sorted(path for path in dist.iterdir() if path.is_file() and path.name != ".gitignore")
    stem = f"henchman_ai-{version}"
    if {path.name for path in files} != {f"{stem}-py3-none-any.whl", f"{stem}.tar.gz"}:
        raise ValueError("Expected exactly the wheel and source distribution for this version")
    if not re.fullmatch(r"[0-9a-f]{40}", commit):
        raise ValueError("Distribution validation requires the tested commit SHA")
    try:
        with zipfile.ZipFile(dist / f"{stem}-py3-none-any.whl") as wheel:
            _validate_contents(
                wheel.read(f"{stem}.dist-info/METADATA"),
                wheel.read("henchman/version.py"),
                wheel.read("henchman/_release.json"),
                version,
                commit,
            )
        with tarfile.open(dist / f"{stem}.tar.gz", "r:gz") as sdist:
            contents = []
            for name in ("PKG-INFO", "src/henchman/version.py", "src/henchman/_release.json"):
                member = sdist.extractfile(f"{stem}/{name}")
                if member is None:
                    raise ValueError("Missing distribution metadata")
                contents.append(member.read())
            _validate_contents(contents[0], contents[1], contents[2], version, commit)
    except (OSError, KeyError, tarfile.TarError, zipfile.BadZipFile, SyntaxError) as error:
        raise ValueError("Invalid release distribution") from error
    return files


def _digest(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def _qualification_step(command: list[str], *, cwd: Path, env: dict[str, str],
                        stdout: BinaryIO, timeout: float) -> None:
    """Own the POSIX release worker's process group through bounded cleanup."""
    if os.name != "posix":
        raise ValueError("Artifact qualification requires the POSIX release worker")
    process = subprocess.Popen(command, cwd=cwd, env=env, stdout=stdout,
                               stderr=subprocess.STDOUT, start_new_session=True)
    try:
        returncode = process.wait(timeout=timeout)
        if returncode:
            raise subprocess.CalledProcessError(returncode, command)
    finally:
        with contextlib.suppress(ProcessLookupError):
            os.killpg(process.pid, signal.SIGTERM)
        deadline = time.monotonic() + 5
        while True:
            process.poll()
            try:
                os.killpg(process.pid, 0)
            except ProcessLookupError:
                break
            if time.monotonic() >= deadline:
                with contextlib.suppress(ProcessLookupError):
                    os.killpg(process.pid, signal.SIGKILL)
                break
            time.sleep(0.02)
        process.wait(timeout=5)


def validate_qualification(dist: Path, version: str, commit: str) -> dict[str, Any]:
    """Require successful installation checks bound to the current archive bytes."""
    try:
        path = dist.parent / "release-evidence/qualification.json"
        if path.stat().st_size > 64 * 1024:
            raise ValueError
        record = json.loads(path.read_text(encoding="utf-8"))
        files = validate_distributions(dist, version, commit)
        hashes = {file.name: _digest(file) for file in files}
        helper = dist.parent / "tests/testing/installed_wheel_smoke.py"
        if (record["schema_version"] != 1 or record["version"] != version
            or record["commit"] != commit or record["artifacts"] != hashes
            or record["profile"] != "installed-wheel-smoke-v1"
            or record["helper_sha256"] != _digest(helper)
            or set(record["runs"]) != {"wheel", "sdist"}):
            raise ValueError
        for kind, run in record["runs"].items():
            suffix = ".whl" if kind == "wheel" else ".tar.gz"
            artifact_hash = next(value for name, value in hashes.items() if name.endswith(suffix))
            if (run["passed"] is not True or run["artifact_sha256"] != artifact_hash
                or not re.fullmatch(r"[0-9a-f]{64}", run["installed_wheel_sha256"])
                or run["python"] != "3.12"):
                raise ValueError
            if kind == "wheel" and run["installed_wheel_sha256"] != artifact_hash:
                raise ValueError
    except (OSError, ValueError, KeyError, TypeError, StopIteration):
        raise ValueError("Missing or mismatched release artifact qualification") from None
    return dict(record)


def qualify_distributions(root: Path, version: str, commit: str) -> None:
    """Install and exercise both archives before writing a hash-bound receipt."""
    root = root.resolve()
    evidence = root / "release-evidence"
    evidence.mkdir(exist_ok=True)
    receipt = evidence / "qualification.json"
    # A failed retry must not inherit an earlier successful record.
    receipt.unlink(missing_ok=True)
    files = validate_distributions(root / "dist", version, commit)
    hashes = {file.name: _digest(file) for file in files}
    helper = root / "tests/testing/installed_wheel_smoke.py"
    helper_hash = _digest(helper)
    environment = dict(os.environ)
    for key in ("PYPI", "UV_PUBLISH_TOKEN", "TWINE_PASSWORD", "PYTHONPATH", "PYTHONHOME"):
        environment.pop(key, None)
    runs = {}
    with tempfile.TemporaryDirectory(prefix="henchman-release-check-") as directory:
        scratch = Path(directory)
        for kind, suffix in (("wheel", ".whl"), ("sdist", ".tar.gz")):
            artifact = next(file for file in files if file.name.endswith(suffix))
            with (evidence / f"{kind}.log").open("wb") as log:
                def run(command: list[str], timeout: int, kind: str = kind) -> None:
                    try:
                        _qualification_step(command, cwd=scratch, env=environment, stdout=log, timeout=timeout)
                    except (OSError, subprocess.SubprocessError):
                        raise ValueError(f"Release {kind} qualification failed; inspect release-evidence/{kind}.log") from None

                wheels = root / "dist"
                if kind == "sdist":
                    wheels = scratch / "sdist-wheel"
                    run(["uv", "build", "--wheel", "--no-sources", "--out-dir", str(wheels), str(artifact)], 600)
                candidates = sorted(wheels.glob("*.whl"))
                if len(candidates) != 1:
                    raise ValueError("Release qualification requires exactly one candidate wheel")
                installed_hash = _digest(candidates[0])
                venv = scratch / f"{kind}-env"
                run(["uv", "venv", "--python", "3.12", "--seed", str(venv)], 180)
                python = venv / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
                run([str(python), "-I", str(helper), "--wheel-dir", str(wheels), "--include-package"], 3600)
                if _digest(candidates[0]) != installed_hash:
                    raise ValueError("Release artifact changed during qualification")
                runs[kind] = {"passed": True, "python": "3.12", "artifact_sha256": hashes[artifact.name],
                              "installed_wheel_sha256": installed_hash}
        if ({file.name: _digest(file) for file in files} != hashes or _digest(helper) != helper_hash):
            raise ValueError("Release artifacts or checks changed during qualification")
    record = {"schema_version": 1, "version": version, "commit": commit,
              "profile": "installed-wheel-smoke-v1", "helper_sha256": helper_hash,
              "artifacts": hashes, "runs": runs}
    temporary = evidence / "qualification.json.tmp"
    temporary.write_text(json.dumps(record, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    temporary.replace(receipt)
    validate_qualification(root / "dist", version, commit)


def publish(dist: Path, version: str) -> int:
    """Publish only the expected distribution pair, preserving upload failures."""
    files = validate_distributions(dist, version, os.environ.get("RELEASE_SHA", ""))
    validate_qualification(dist, version, os.environ.get("RELEASE_SHA", ""))
    environment = os.environ.copy()
    token = parse_pypi_token(environment.pop("PYPI", ""))
    # GitHub masks the whole INI secret; mask its extracted token independently.
    if os.environ.get("GITHUB_ACTIONS") == "true":
        print(f"::add-mask::{token}", flush=True)
    environment["UV_PUBLISH_TOKEN"] = token
    return subprocess.run(
        [
            "uv",
            "publish",
            "--publish-url",
            "https://upload.pypi.org/legacy/",
            "--check-url",
            "https://pypi.org/simple/",
            *map(str, files),
        ],
        env=environment,
        check=False,
    ).returncode


def main() -> int:
    """Run release validation or publication without installing the package."""
    try:
        version = validate_release(Path.cwd(), os.environ.get("RELEASE_MILESTONE", ""))
        if sys.argv[1:] == ["prepare"]:
            prepare_provenance(
                Path.cwd(),
                version,
                os.environ.get("RELEASE_SHA", ""),
                os.environ.get("RELEASE_PR", ""),
            )
            return 0
        if sys.argv[1:] == ["check"]:
            with Path(os.environ["GITHUB_OUTPUT"]).open("a", encoding="utf-8") as output:
                output.write(f"version={version}\ntag=v{version}\n")
            return 0
        if sys.argv[1:] == ["publish"]:
            return publish(Path("dist"), version)
        if sys.argv[1:] == ["qualify"]:
            qualify_distributions(Path.cwd(), version, os.environ.get("RELEASE_SHA", ""))
            return 0
        raise ValueError("Use check, prepare, qualify, or publish")
    except ValueError as error:
        print(str(error), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
