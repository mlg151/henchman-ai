"""Validate milestone releases and publish using the repository's INI secret."""

import configparser
import os
import re
import runpy
import subprocess
import sys
import tomllib
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


def publish(dist: Path, version: str) -> int:
    """Publish only the expected distribution pair, preserving upload failures."""
    files = sorted(path for path in dist.iterdir() if path.is_file())
    expected = {f"henchman_ai-{version}-py3-none-any.whl", f"henchman_ai-{version}.tar.gz"}
    if {path.name for path in files} != expected:
        raise ValueError("Expected exactly the wheel and source distribution for this version")
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
        if sys.argv[1:] == ["check"]:
            with Path(os.environ["GITHUB_OUTPUT"]).open("a", encoding="utf-8") as output:
                output.write(f"version={version}\ntag=v{version}\n")
            return 0
        if sys.argv[1:] == ["publish"]:
            return publish(Path("dist"), version)
        raise ValueError("Use check or publish")
    except ValueError as error:
        print(str(error), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
