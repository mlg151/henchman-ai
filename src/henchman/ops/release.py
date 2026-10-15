"""Validate milestone releases and publish using the repository's INI secret."""

import ast
import configparser
import email
import json
import os
import re
import runpy
import subprocess
import sys
import tarfile
import tomllib
import zipfile
from pathlib import Path


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


def publish(dist: Path, version: str) -> int:
    """Publish only the expected distribution pair, preserving upload failures."""
    files = validate_distributions(dist, version, os.environ.get("RELEASE_SHA", ""))
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
        raise ValueError("Use check, prepare, or publish")
    except ValueError as error:
        print(str(error), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
