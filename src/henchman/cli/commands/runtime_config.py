"""Read-only slash adapters for the shared configuration and doctor surfaces."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from henchman.cli.commands import Command, CommandContext
from henchman.cli.commands.config_view_command import build_config_value_payload
from henchman.cli.commands.doctor_command import collect_doctor_report, render_doctor_text
from henchman.cli.evidence import runtime_evidence_redactor
from henchman.config.repository import SettingsRepository, SettingsScope
from henchman.config.runtime import runtime_settings_state


def _runtime_repository(ctx: CommandContext) -> tuple[Any, SettingsRepository]:
    runtime = ctx.repl if ctx.repl is not None else ctx
    state = runtime_settings_state(runtime)
    return runtime, SettingsRepository(Path.cwd(), snapshot_provider=state.snapshot)


class RuntimeConfigCommand(Command):
    """Inspect live settings, or explicitly inspect one persisted file scope."""

    @property
    def name(self) -> str:
        return "config"

    @property
    def description(self) -> str:
        return "Inspect live settings and their origins"

    @property
    def usage(self) -> str:
        return "/config <view|get> KEY [--scope merged|global|project]"

    async def execute(self, ctx: CommandContext) -> None:
        args = ctx.args
        if len(args) not in (2, 4) or args[0] not in ("get", "view"):
            ctx.console.print(f"Usage: {self.usage}", markup=False)
            return
        scope = SettingsScope.MERGED
        if len(args) == 4:
            if args[2] != "--scope":
                ctx.console.print(f"Usage: {self.usage}", markup=False)
                return
            scope = SettingsScope(args[3])
        runtime, repository = _runtime_repository(ctx)
        policy = runtime_evidence_redactor(runtime)
        payload = build_config_value_payload(
            repository=repository, key_path=args[1], scope=scope, redactor=policy,
        )
        safe = payload.as_mapping()
        safe["key"] = policy.text(payload.key)
        ctx.console.print(yaml.safe_dump(safe, sort_keys=False), end="", markup=False, highlight=False)


class RuntimeDoctorCommand(Command):
    """Run the existing diagnostic collectors against the active snapshot."""

    @property
    def name(self) -> str:
        return "doctor"

    @property
    def description(self) -> str:
        return "Inspect runtime configuration and tool health"

    @property
    def usage(self) -> str:
        return "/doctor"

    async def execute(self, ctx: CommandContext) -> None:
        if ctx.args:
            ctx.console.print(f"Usage: {self.usage}", markup=False)
            return
        runtime, repository = _runtime_repository(ctx)
        report = collect_doctor_report(
            settings_repository=repository,
            registered_tool_names=ctx.tool_registry.list_tools() if ctx.tool_registry else None,
        )
        rendered = runtime_evidence_redactor(runtime).text(render_doctor_text(report))
        ctx.console.print(rendered, markup=False, highlight=False)
