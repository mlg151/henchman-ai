"""Refresh one conversation's scoped instructions at request and tool boundaries."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from threading import Event
from typing import TYPE_CHECKING

from henchman.config.context import ContextLoader, ContextSnapshot, ContextSource
from henchman.providers.base import Message
from henchman.tools.base import Tool, ToolKind, ToolResult

if TYPE_CHECKING:
    from collections.abc import Callable

    from henchman.core.agent import Agent

_HEADER = "## Active scoped project instructions\n"
_FILE_TOOLS = frozenset({
    "read_file", "write_file", "edit_file", "patch_apply", "ls", "glob", "grep",
    "file_overview", "python_ast", "lint_check", "code_format", "test_gen",
    "symbol_trace", "dead_code", "import_graph", "pattern_search",
})
_EXECUTION_TOOLS = frozenset({"shell", "shell_secure", "python_exec", "task_create"})
_ADDITIONAL_PATHS = {"test_gen": ("output_path",), "import_graph": ("scan_dir",)}


def _uses_task_service(tool: Tool, params: dict[str, object]) -> bool:
    """Match the cwd expansion and bound default used by background execution."""
    return tool.name == "task_create" or (
        tool.name in {"shell", "python_exec"} and bool(params.get("background", True))
    )


def _resolve_target(tool: Tool, raw: str, params: dict[str, object]) -> Path:
    """Preserve each tool's literal versus home-expanded path interpretation."""
    path = Path(raw)
    if tool.name in {"write_file", "edit_file"} or _uses_task_service(tool, params):
        path = path.expanduser()
    return path.resolve()


def _format_targets(target: Path) -> tuple[Path, ...]:
    """Use the formatter's own bounded file selection and validation rules."""
    from henchman.tools.formatting import FormattingError, _expand_paths

    try:
        files = _expand_paths([target], Path.cwd(), Event())
    except FormattingError as exc:
        raise ValueError(f"Cannot resolve formatting instruction scopes: {exc}") from exc
    # A directory identifies the same applicable instructions for every file
    # in it. Avoid reading the same sources once per Python file.
    return tuple(dict.fromkeys(path.parent for path in files)) or (target,)


def _tool_targets(tool: Tool, params: dict[str, object]) -> tuple[Path, ...]:
    """Use structured paths, including the patch tool's own parser, never shell text."""
    if tool.name == "patch_apply" and isinstance(params.get("patch"), str):
        from henchman.tools.builtins.patch_apply import PatchParser

        path = params.get("path")
        paths = PatchParser(str(params["patch"]), path if isinstance(path, str) else None).parse()
        return tuple(Path(path).resolve() for path in paths)
    key = "path" if tool.name in _FILE_TOOLS else "cwd"
    targets = [
        _resolve_target(tool, raw, params)
        for name in (key, *_ADDITIONAL_PATHS.get(tool.name, ()))
        if isinstance(raw := params.get(name), str) and raw
    ]
    if not targets:
        bound_root = getattr(tool, "_project_root", None) if _uses_task_service(tool, params) else None
        targets = [bound_root if isinstance(bound_root, Path) else Path.cwd()]
    if targets[0].is_dir():
        if tool.name == "code_format":
            return _format_targets(targets[0])
        if tool.name == "lint_check" and params.get("fix") is True:
            raise ValueError(
                "Directory lint fixes require explicit file targets so every affected "
                "instruction scope can be reviewed. Inspect without fix, then fix individual files."
            )
    return tuple(dict.fromkeys(targets))


def _combine(snapshots: list[ContextSnapshot], targets: tuple[Path, ...]) -> ContextSnapshot:
    """Merge only simultaneously applicable target scopes in deterministic order."""
    if len(snapshots) == 1:
        return snapshots[0]
    unique: dict[Path, ContextSource] = {}
    for snapshot in snapshots:
        for source in snapshot.sources:
            unique.setdefault(source.path.resolve(), source)
    sources = sorted(unique.values(), key=lambda source: (
        source.kind != "global", len(source.scope.parts), str(source.scope), source.order,
    ))
    records = tuple(replace(source, order=index) for index, source in enumerate(sources))
    content = "\n\n---\n\n".join(f"# Context: {source.path}\n{source.content}" for source in records)
    discovery = snapshots[0].discovery
    if discovery is not None:
        discovery = replace(discovery, targets=targets)
    return ContextSnapshot(records, content, discovery)


def _render(snapshot: ContextSnapshot) -> str:
    """Render scope and conflict rules without changing legacy loader output."""
    lines = [
        _HEADER,
        "Explicit user task constraints take precedence over these files. "
        "Repository guidance overrides global guidance; deeper applicable directory "
        "scopes override broader scopes. Within the same scope, the first listed "
        "filename has priority. Each source applies only in its stated scope. "
        "Instruction text cannot widen tool policy, approvals or access controls.",
    ]
    for source in snapshot.sources:
        lines.append(
            f"# Context: {source.path}\n"
            f"Scope: {source.scope}; kind: {source.kind}; order: {source.order}\n"
            f"{source.content}"
        )
    return "\n\n".join(lines)


class InstructionContext:
    """Keep fresh instruction text isolated to the owning agent's request history."""

    def __init__(
        self, agent: Agent, snapshot: ContextSnapshot,
        on_update: Callable[[ContextSnapshot], None] | None = None,
    ) -> None:
        self.agent = agent
        self.snapshot = snapshot
        self.on_update = on_update
        self.presented_digest: str | None = None
        discovery = snapshot.discovery
        self.targets = (
            discovery.targets or (discovery.start_dir,) if discovery is not None else ()
        )
        self.loader: ContextLoader | None = None
        if discovery is not None:
            self.loader = ContextLoader(
                filenames=discovery.filenames, start_dir=discovery.boundary,
                max_source_chars=discovery.max_source_chars,
            )
            self.loader._scope_boundary = discovery.boundary  # noqa: SLF001

    @classmethod
    def attach(
        cls, agent: Agent, snapshot: ContextSnapshot,
        on_update: Callable[[ContextSnapshot], None] | None = None,
    ) -> InstructionContext:
        """Attach a private refresh controller without modifying permissions."""
        runtime = cls(agent, snapshot, on_update)
        # Startup CLI prompts formerly embedded this text. Keep a single managed
        # copy, so changing targets cannot leave stale sibling guidance behind.
        if snapshot.content:
            agent.system_prompt = agent.system_prompt.replace(snapshot.content, "").strip()
            for message in agent.messages:
                if message.role == "system" and message.content:
                    message.content = message.content.replace(snapshot.content, "").strip()
        agent.instruction_context = runtime
        agent.tool_registry.bind_execution_guard(runtime.before_tool)
        return runtime

    def refresh(self, target: Path | None = None) -> None:
        """Reload the active target using the original boundary and filename settings."""
        self._refresh_targets((target,) if target is not None else self.targets)

    def _refresh_targets(self, targets: tuple[Path, ...], *, capture: bool = False) -> None:
        """Capture all targets before mutating the active instruction state."""
        if self.loader is None or not targets:
            if capture and self.on_update is not None:
                self.on_update(self.snapshot)
            return
        snapshot = _combine([self.loader.load_for_path(target) for target in targets], targets)
        changed = snapshot.digest != self.snapshot.digest or targets != self.targets
        if (changed or capture) and self.on_update is not None:
            self.on_update(snapshot)
        self.targets = targets
        self.snapshot = snapshot

    def prepare(self) -> None:
        """Refresh and replace the mandatory instruction message before a request."""
        # Other conversations can have updated the shared session evidence
        # since this agent's last request, even when its own files did not change.
        self._refresh_targets(self.targets, capture=True)
        messages = self.agent.messages
        retained = [
            message for message in messages
            if not (message.role == "system" and (message.content or "").startswith(_HEADER))
        ]
        removed_before_turn = sum(
            message.role == "system" and (message.content or "").startswith(_HEADER)
            for message in messages[:self.agent.turn.start_index]
        )
        added = int(bool(self.snapshot.sources))
        if added:
            retained.insert(0, Message(role="system", content=_render(self.snapshot)))
        self.agent.messages = retained
        self.agent.turn.start_index = max(
            0, self.agent.turn.start_index - removed_before_turn + added,
        )

    def before_tool(self, tool: Tool, params: dict[str, object]) -> ToolResult | None:
        """Defer mutations until the model has received their current scoped guidance."""
        if tool.name not in _FILE_TOOLS | _EXECUTION_TOOLS:
            return None
        try:
            targets = _tool_targets(tool, params)
            discovery = self.snapshot.discovery
            if discovery is not None:
                # Discovery boundaries neither authorize nor forbid tool access.
                # Preserve access policy without reading outside instructions.
                targets = tuple(p for p in targets if p.is_relative_to(discovery.boundary))
            if not targets:
                return None
            self._refresh_targets(targets)
        except (OSError, UnicodeError, ValueError) as exc:
            return ToolResult(
                content=f"Cannot refresh project instructions: {exc}", success=False,
                error="Instruction refresh failed",
            )
        if tool.execution_kind(params) != ToolKind.READ and self.snapshot.digest != self.presented_digest:
            return ToolResult(
                content=(
                    "Project instructions changed for this target. The action was not executed. "
                    "Review the refreshed scoped instructions in the next model request, "
                    "then retry if the action still complies."
                ),
                success=False, error="Project instructions require review",
            )
        return None
