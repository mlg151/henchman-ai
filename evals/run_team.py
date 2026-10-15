"""Run the opt-in Python team evaluation and retain a report outside its workspace."""

from __future__ import annotations

import argparse
import asyncio
import inspect
import json
import math
import os
import sys
from datetime import UTC, datetime
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any

from evals.helpers import EvalTestRig
from henchman.config import load_settings
from henchman.config.schema import Settings
from henchman.providers.factory import create_configured_provider


def _positive_integer(value: str) -> int:
    number = int(value)
    if number <= 0:
        raise argparse.ArgumentTypeError("must be a positive integer")
    return number


def _round_limit(value: str) -> int:
    number = int(value)
    if number < 0:
        raise argparse.ArgumentTypeError("must be a nonnegative integer")
    return number


def _timeout(value: str) -> float:
    number = float(value)
    if not math.isfinite(number) or number <= 0:
        raise argparse.ArgumentTypeError("must be a finite positive number")
    return number


def _arguments(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--scenario",
        choices=("workflow", "package"),
        default="workflow",
        help="Python workflow or offline package/install task",
    )
    parser.add_argument("--provider", default="openrouter")
    parser.add_argument("--model", help="Override the selected provider's saved model")
    parser.add_argument(
        "--context-length",
        type=_positive_integer,
        help="Override saved raw context capacity for this evaluation",
    )
    parser.add_argument(
        "--max-iterations",
        type=_round_limit,
        default=25,
        help="Maximum tool rounds per agent (default: 25)",
    )
    parser.add_argument(
        "--timeout",
        type=_timeout,
        default=300.0,
        help="Whole agent-turn deadline in seconds (default: 300)",
    )
    parser.add_argument("--report", type=Path, required=True)
    return parser.parse_args(argv)


async def run_team_python_workflow(
    rig: EvalTestRig,
    *,
    max_iterations: int,
    timeout: float,
) -> dict[str, Any]:
    """Load the scenario after configuration, avoiding eval collection on --help."""
    from evals.test_team_python_workflow import run_team_python_workflow as scenario

    return await scenario(rig, max_iterations=max_iterations, timeout=timeout)


async def run_team_python_package(
    rig: EvalTestRig,
    *,
    max_iterations: int,
    timeout: float,
) -> dict[str, Any]:
    """Load the offline package task only when explicitly selected."""
    from evals.test_team_python_package import run_team_python_package as scenario

    return await scenario(rig, max_iterations=max_iterations, timeout=timeout)


def _secrets(settings: Settings | None) -> set[str]:
    """Collect configured credentials solely for removing them from diagnostics."""
    values = {
        value for key, value in os.environ.items() if key.endswith(("_API_KEY", "_TOKEN")) and value
    }
    if settings is not None:
        for config in settings.providers.model_dump().values():
            if isinstance(config, dict):
                for key in ("api_key", "token", "access_token"):
                    value = config.get(key)
                    if isinstance(value, str) and value:
                        values.add(value)
                        if value.startswith("${") and value.endswith("}"):
                            resolved = os.environ.get(value[2:-1])
                            if resolved:
                                values.add(resolved)
    return values


def _redact(value: Any, secrets: set[str]) -> Any:
    """Remove credential values without serializing provider objects or settings."""
    if isinstance(value, str):
        for secret in sorted(secrets, key=len, reverse=True):
            value = value.replace(secret, "[redacted]")
        return value
    if isinstance(value, dict):
        return {key: _redact(item, secrets) for key, item in value.items()}
    if isinstance(value, list):
        return [_redact(item, secrets) for item in value]
    return value


def _error(exc: BaseException) -> dict[str, str]:
    return {"type": type(exc).__name__, "message": str(exc)}


def _environment() -> dict[str, Any]:
    """Record comparable interpreter and checker versions without host secrets."""
    packages: dict[str, str | None] = {}
    for name in ("henchman-ai", "openai", "anthropic", "pytest", "black", "ruff", "mypy"):
        try:
            packages[name] = version(name)
        except PackageNotFoundError:
            packages[name] = None
    return {"python": sys.version.split()[0], "platform": sys.platform, "packages": packages}


async def _close_clients(providers: list[Any]) -> list[dict[str, str]]:
    """Close distinct SDK clients constructed for this standalone experiment."""
    closed: set[int] = set()
    errors: list[dict[str, str]] = []
    for provider in providers:
        client = getattr(provider, "_client", None)
        close = getattr(client, "close", None)
        if not callable(close) or id(client) in closed:
            continue
        closed.add(id(client))
        try:
            outcome = close()
            if inspect.isawaitable(outcome):
                await outcome
        except (Exception, asyncio.CancelledError) as exc:
            errors.append(_error(exc))
    return errors


async def _evaluate(args: argparse.Namespace) -> tuple[dict[str, Any], int]:
    report: dict[str, Any] = {
        "schema_version": 1,
        "environment": _environment(),
        "started_at": datetime.now(UTC).isoformat(),
        "requested": {
            "scenario": args.scenario,
            "provider": args.provider,
            "model": args.model,
            "context_length": args.context_length,
            "max_iterations": args.max_iterations,
            "timeout": args.timeout,
        },
        "profile": None,
        "result": None,
        "success": False,
        "task_verified": False,
        "usage": None,
        "cost": None,
        "error": None,
    }
    settings: Settings | None = None
    providers: list[Any] = []
    rig: EvalTestRig | None = None
    code = 2
    try:
        settings = load_settings(project_root=Path.cwd()).model_copy(deep=True)
        if args.context_length is not None:
            settings.context.max_tokens = args.context_length
        provider = create_configured_provider(
            settings.providers,
            provider_name=args.provider,
            model=args.model,
        )
        providers.append(provider)
        rig = EvalTestRig(provider=provider, profile="team", settings=settings)
        rig.setup(f"team-python-{args.scenario}")
        report["profile"] = rig.profile_metadata
        code = 1
        scenario = (
            run_team_python_package if args.scenario == "package" else run_team_python_workflow
        )
        result = await scenario(
            rig,
            max_iterations=args.max_iterations,
            timeout=args.timeout,
        )
        if not isinstance(result, dict) or type(result.get("success")) is not bool:
            raise ValueError("The scenario did not return a valid success result")
        report.update(result=result, success=result["success"], profile=rig.profile_metadata)
        code = 0 if result["success"] else 1
    except asyncio.CancelledError:
        report["error"] = {"type": "CancelledError", "message": "Evaluation cancelled."}
        code = 130
    except Exception as exc:
        report["error"] = _error(exc)
        if settings is None:
            report["error"][
                "message"
            ] = "Unable to load settings; check configuration types and values."
    finally:
        errors: list[dict[str, str]] = []
        try:
            if rig is not None:
                try:
                    providers.extend(rig.providers)
                except Exception as exc:
                    errors.append(_error(exc))
            errors.extend(await _close_clients(providers))
        finally:
            if rig is not None:
                try:
                    rig.cleanup()
                except Exception as exc:
                    errors.append(_error(exc))
        if errors:
            report.update(success=False, cleanup_errors=errors)
            if report["error"] is None:
                report["error"] = errors[0]
            code = 1
        report["finished_at"] = datetime.now(UTC).isoformat()
    return _redact(report, _secrets(settings)), code


def _write_report(path: Path, report: dict[str, Any]) -> None:
    """Replace a report only after a complete JSON document is ready."""
    content = (
        json.dumps(report, indent=2, sort_keys=True, ensure_ascii=True, allow_nan=False) + "\n"
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary: Path | None = None
    try:
        with NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=path.parent, delete=False
        ) as stream:
            temporary = Path(stream.name)
            stream.write(content)
        temporary.replace(path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def main(argv: list[str] | None = None) -> int:
    """Run one explicit experiment; return nonzero when any required part fails."""
    args = _arguments(argv)
    path = args.report.expanduser().resolve()
    report, code = asyncio.run(_evaluate(args))
    try:
        _write_report(path, report)
    except (OSError, TypeError, ValueError) as exc:
        print(f"Could not write evaluation report ({type(exc).__name__}).", file=sys.stderr)
        return 2
    outcome = "passed" if report["success"] else "failed"
    print(f"Team Python evaluation {outcome}; report: {path}")
    return code


if __name__ == "__main__":
    raise SystemExit(main())
