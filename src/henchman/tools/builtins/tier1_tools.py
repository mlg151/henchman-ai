"""Tier 1 builtin tools for discovery and local invocation primitives."""

from __future__ import annotations

import asyncio
import importlib
import inspect
from collections.abc import Awaitable, Callable, Iterable, Mapping
from copy import copy
from pathlib import Path
from typing import TYPE_CHECKING

from henchman.cli.commands.discovery_capabilities import (
    build_discovery_capabilities,
    classify_registered_tool,
)
from henchman.skills import SkillCatalog, SkillDefinition
from henchman.tools.base import Tool, ToolKind, ToolResult
from henchman.tools.builtins.shell import ShellTool
from henchman.tools.builtins.web_search import DuckDuckGoSearchTool

if TYPE_CHECKING:
    from henchman.tools.registry import ToolRegistry

_DEFAULT_SHELL_TIMEOUT = 60
_DEFAULT_SLEEP_MIN_SECONDS = 0.0
_DEFAULT_SLEEP_MAX_SECONDS = 60.0
_DEFAULT_SEARCH_LIMIT = 5
_MAX_SEARCH_LIMIT = 100

_SEARCH_PARAMETERS: dict[str, object] = {
    "type": "object",
    "properties": {
        "query": {
            "type": "string",
            "description": (
                "Agent scope: match tool names and descriptions. "
                "Team scope: one exact, nonempty tool name."
            ),
        },
        "scope": {
            "type": "string",
            "enum": ["agent", "team"],
            "default": "agent",
            "description": "Search this agent's tools or role-only team capability metadata.",
        },
        "limit": {
            "type": "integer",
            "description": "Maximum entries per page (default 5).",
            "default": _DEFAULT_SEARCH_LIMIT,
            "minimum": 1,
            "maximum": _MAX_SEARCH_LIMIT,
        },
        "offset": {
            "type": "integer",
            "description": "Entry offset; use next_offset to browse the next page.",
            "default": 0,
            "minimum": 0,
        },
    },
}

_SKILL_PARAMETERS: dict[str, object] = {
    "type": "object",
    "properties": {
        "skill": {
            "type": "string",
            "description": "Name of the bundled skill to invoke.",
        }
    },
    "required": ["skill"],
}

_SLEEP_PARAMETERS: dict[str, object] = {
    "type": "object",
    "properties": {
        "seconds": {
            "type": "number",
            "description": "Number of seconds to pause, within validated bounds.",
        }
    },
    "required": ["seconds"],
}

_ToolClassResolver = Callable[[], Iterable[type[Tool]]]
_SleepCallable = Callable[[float], Awaitable[None]]
_SkillHandler = Callable[[], ToolResult | Awaitable[ToolResult]]


def _default_tool_class_resolver() -> tuple[type[Tool], ...]:
    """Return the builtin tool classes exported through the shared surface."""
    builtins_module = importlib.import_module("henchman.tools.builtins")
    return tuple(builtins_module.iter_available_builtin_tool_classes())


def _instantiate_tool(tool_class: type[Tool]) -> Tool:
    """Instantiate a builtin tool class for metadata-only discovery."""
    if tool_class is ShellTool:
        return ShellTool(default_timeout=_DEFAULT_SHELL_TIMEOUT)
    return tool_class()


def _normalize_query(raw_query: object) -> tuple[str, ...]:
    """Normalize a search query into casefolded tokens."""
    return tuple(token.casefold() for token in str(raw_query).split() if token)


def _matches_query(*, query_tokens: tuple[str, ...], text: str) -> bool:
    """Return whether all query tokens appear in *text*."""
    if not query_tokens:
        return True
    normalized_text = text.casefold()
    return all(token in normalized_text for token in query_tokens)


def _coerce_seconds(raw_seconds: object) -> float | None:
    """Convert a user-provided seconds value into a float when possible."""
    if isinstance(raw_seconds, bool) or not isinstance(raw_seconds, int | float | str):
        return None
    try:
        return float(raw_seconds)
    except (TypeError, ValueError):
        return None


class ToolSearchTool(Tool):
    """Search the builtin Tier 1 tool surface by name and description."""

    def __init__(self, tool_class_resolver: _ToolClassResolver | None = None) -> None:
        """Initialize the tool with an optional custom tool resolver.

        Args:
            tool_class_resolver: Optional callable returning the exported tool
                classes that should be searched. Defaults to the builtin export
                surface.
        """
        self._tool_class_resolver = tool_class_resolver or _default_tool_class_resolver
        self._tool_registry: ToolRegistry | None = None

    def bind_runtime(
        self,
        *,
        tool_registry: ToolRegistry | None = None,
        **_: object,
    ) -> None:
        """Bind the live registry used for runtime discovery.

        Args:
            tool_registry: Registry whose current tools should be searched.
            **_: Other shared runtime dependencies unused by this tool.
        """
        self._tool_registry = tool_registry
        if tool_registry is not None:
            tool_registry.enable_tool_discovery(self)

    def for_registry(self, registry: ToolRegistry) -> ToolSearchTool:
        """Copy search configuration while binding an independent registry scope."""
        scoped = copy(self)
        scoped.bind_runtime(tool_registry=registry)
        return scoped

    def _resolve_tools(self) -> tuple[Tool, ...]:
        """Return current runtime tools or metadata-only builtin instances."""
        if self._tool_registry is None:
            return tuple(
                _instantiate_tool(tool_class) for tool_class in self._tool_class_resolver()
            )
        return tuple(
            tool
            for name in self._tool_registry.list_tools()
            if (tool := self._tool_registry.get(name)) is not None
        )

    @property
    def name(self) -> str:
        """Return the unique tool identifier."""
        return "tool_search"

    @property
    def description(self) -> str:
        """Return a human-readable tool description."""
        return (
            "Search this agent's available tools by name and description. Exposes matching tool "
            "schemas when context limits hide the catalog; use an exact tool name "
            "to prioritize its schema. With scope=team and an exact tool name, "
            "find enabled roles whose live scopes contain it, without granting tool access. "
            "Results are paginated (default 5 entries)."
        )

    @property
    def parameters(self) -> dict[str, object]:
        """Return the JSON Schema for tool search parameters."""
        return _SEARCH_PARAMETERS

    @property
    def kind(self) -> ToolKind:
        """Return the tool kind used for confirmation policies."""
        return ToolKind.READ

    async def execute(self, **params: object) -> ToolResult:
        """Execute a search over the builtin tool export surface.

        Args:
            **params: Optional ``scope`` (agent/team), ``query``, ``limit``, and
                ``offset``. Team scope requires one exact, nonempty tool name.

        Returns:
            Matching tool entries rendered as deterministic text.
        """
        try:
            scope, query = _search_scope_query(params)
            limit, offset = _search_pagination(params)
        except ValueError as exc:
            return ToolResult(content=str(exc), success=False, error=str(exc))
        if scope == "team":
            return self._search_team(query, limit=limit, offset=offset)
        query_tokens = _normalize_query(query)
        tools = self._resolve_tools()
        registered_tool_names = tuple(tool.name for tool in tools)
        matched_tools: list[Tool] = []

        for tool in tools:
            searchable_text = _build_tool_search_text(
                tool,
                registered_tool_names=registered_tool_names,
            )
            if _matches_query(query_tokens=query_tokens, text=searchable_text):
                matched_tools.append(tool)

        matched_capability_entries = _collect_capability_search_entries(
            query_tokens=query_tokens,
            registered_tool_names=registered_tool_names,
        )

        if not matched_tools and not matched_capability_entries:
            search_scope = (
                "this agent's scope"
                if self._tool_registry is not None
                else "the builtin discovery catalog"
            )
            return ToolResult(
                content=(
                    f'No tools or capability classifications matched "{query}". '
                    f"Only {search_scope} was searched; this does not establish team-wide absence. "
                    "Use scope=team with an exact tool name to look up enabled roles, "
                    "or broaden this search to browse available pages."
                ),
                success=False,
                error="No matching tools found",
            )

        matched_tools.sort(
            key=lambda tool: (
                tool.name.casefold() != query.casefold(),
                tool.name.casefold(),
            )
        )
        matched_capability_entries.sort()
        lines, names = _render_search_page(
            matched_tools,
            matched_capability_entries,
            registered_tool_names=registered_tool_names,
            query=query,
            limit=limit,
            offset=offset,
        )
        if self._tool_registry is not None and names:
            self._tool_registry.prioritize_tools(names)
            lines.append(
                "Prioritized schemas: "
                + ", ".join(self._tool_registry.discovered_tools)
                + ". Search an exact tool name to narrow schema discovery."
            )
        return ToolResult(content="\n".join(lines))

    def _search_team(self, query: str, *, limit: int, offset: int) -> ToolResult:
        """Return paginated role names without changing executable tool discovery."""
        roles = (
            self._tool_registry.find_team_tool_roles(query)
            if self._tool_registry is not None
            else None
        )
        if roles is None:
            message = "Team tool lookup unavailable: this agent needs a bound team and delegate_task in its scope."
            return ToolResult(content=message, success=False, error=message)
        roles = sorted(set(roles))
        lines = [f'Team role scope metadata for exact tool "{query}":']
        lines.extend(f"- {role}" for role in roles[offset : offset + limit])
        if not roles:
            lines.append("No enabled candidate has this exact tool in its current scope.")
        next_offset = str(offset + limit) if offset + limit < len(roles) else "none"
        lines.append(
            f"Page: total={len(roles)} offset={offset} limit={limit} next_offset={next_offset}"
        )
        lines.append(
            "Scope metadata only; not an authorization, model-readiness or current-availability guarantee. "
            "No tool access, schemas or approvals were added."
        )
        return ToolResult(content="\n".join(lines))


def _search_scope_query(params: dict[str, object]) -> tuple[str, str]:
    """Validate scope and query before accessing a resolver or discovery state."""
    scope = params.get("scope", "agent")
    if not isinstance(scope, str) or scope not in ("agent", "team"):
        raise ValueError("scope must be 'agent' or 'team'.")
    query = params.get("query", "")
    if not isinstance(query, str):
        raise ValueError("query must be a string.")
    query = query.strip()
    if scope == "team" and (not query or any(character.isspace() for character in query)):
        raise ValueError("Team scope requires one exact, nonempty tool name.")
    return scope, query


def _search_pagination(params: dict[str, object]) -> tuple[int, int]:
    """Validate pagination before querying tools or changing discovery priorities."""
    limit = params.get("limit", _DEFAULT_SEARCH_LIMIT)
    offset = params.get("offset", 0)
    if type(limit) is not int or not 1 <= limit <= _MAX_SEARCH_LIMIT:
        raise ValueError(f"limit must be an integer between 1 and {_MAX_SEARCH_LIMIT}.")
    if type(offset) is not int or offset < 0:
        raise ValueError("offset must be a nonnegative integer.")
    return limit, offset


def _render_search_page(
    tools: list[Tool],
    capabilities: list[str],
    *,
    registered_tool_names: tuple[str, ...],
    query: str,
    limit: int,
    offset: int,
) -> tuple[list[str], list[str]]:
    """Page across tools followed by capability truth, preserving their ordering."""
    end = offset + limit
    page_tools = tools[offset:end]
    page_capabilities = capabilities[max(0, offset - len(tools)) : max(0, end - len(tools))]
    lines = ["Available tools:" if not query else f'Tools matching "{query}":']
    lines.extend(
        _render_tool_search_entry(tool, registered_tool_names=registered_tool_names)
        for tool in page_tools
    )
    if page_capabilities:
        lines.extend(["Capability truth:", *page_capabilities])
    total = len(tools) + len(capabilities)
    next_offset = str(end) if end < total else "none"
    lines.append(f"Page: total={total} offset={offset} limit={limit} next_offset={next_offset}")
    if end < total:
        lines.append(f"Use offset={end} with the same query to browse the next page.")
    elif offset >= total:
        lines.append("No entries at this offset; use offset=0 to browse from the start.")
    names = [tool.name for tool in page_tools if tool.name != "tool_search"]
    return lines, names


def _build_tool_search_text(
    tool: Tool,
    *,
    registered_tool_names: tuple[str, ...],
) -> str:
    """Return searchable text for one tool entry."""

    capability = classify_registered_tool(
        tool.name,
        registered_tool_names=registered_tool_names,
    )
    parts = [tool.name, tool.description]
    if capability is not None:
        parts.extend(
            (
                capability.classification,
                capability.summary,
                capability.detail,
                *capability.aliases,
            )
        )
    return " ".join(parts)


def _render_tool_search_entry(
    tool: Tool,
    *,
    registered_tool_names: tuple[str, ...],
) -> str:
    """Render one matched tool entry with discovery classification when available."""

    capability = classify_registered_tool(
        tool.name,
        registered_tool_names=registered_tool_names,
    )
    if capability is None:
        return f"- {tool.name}: {tool.description}"
    return f"- {tool.name} [{capability.classification}]: {tool.description}"


def _collect_capability_search_entries(
    *,
    query_tokens: tuple[str, ...],
    registered_tool_names: tuple[str, ...],
) -> list[str]:
    """Return capability-truth entries matching the current query."""

    entries: list[str] = []
    seen_names = {
        capability.name
        for capability in (
            classify_registered_tool(tool_name, registered_tool_names=registered_tool_names)
            for tool_name in registered_tool_names
        )
        if capability is not None
    }

    for capability in build_discovery_capabilities(
        registered_tool_names=registered_tool_names,
    ):
        if capability.name in seen_names:
            continue
        if _matches_query(query_tokens=query_tokens, text=capability.search_text):
            entries.append(
                f"- {capability.name} [{capability.classification}]: {capability.summary}"
            )
    return entries


class SkillTool(Tool):
    """Invoke a bundled local skill without marketplace expansion."""

    def __init__(
        self,
        skill_handlers: Mapping[str, _SkillHandler] | None = None,
        *,
        skill_catalog: SkillCatalog | None = None,
    ) -> None:
        """Initialize the tool with optional bundled skill handlers.

        Args:
            skill_handlers: Optional mapping of skill name to local handler.
                Handler names are normalized case-insensitively.
            skill_catalog: Optional compatible on-disk skills catalog.
        """
        provided_handlers = skill_handlers or {}
        self._skill_handlers = {
            skill_name.casefold(): handler for skill_name, handler in provided_handlers.items()
        }
        self._available_skills = tuple(sorted(provided_handlers))
        self._skill_catalog = skill_catalog or SkillCatalog()

    def bind_runtime(
        self,
        *,
        project_root: Path | None = None,
        **_: object,
    ) -> None:
        """Bind the current project root so compatible skills resolve correctly."""

        if project_root is not None:
            self._skill_catalog.set_project_root(project_root)

    @property
    def name(self) -> str:
        """Return the unique tool identifier."""
        return "skill"

    @property
    def description(self) -> str:
        """Return a human-readable tool description."""
        return "Invoke a bundled local skill by name."

    @property
    def parameters(self) -> dict[str, object]:
        """Return the JSON Schema for skill invocation parameters."""
        return _SKILL_PARAMETERS

    @property
    def kind(self) -> ToolKind:
        """Return the tool kind used for confirmation policies."""
        return ToolKind.READ

    async def execute(self, **params: object) -> ToolResult:
        """Dispatch a known bundled skill handler.

        Args:
            **params: Tool parameters containing the required ``skill`` name.

        Returns:
            The handler's ``ToolResult`` or a deterministic failure payload.
        """
        skill_name = str(params.get("skill", "")).strip()
        if not skill_name:
            return ToolResult(
                content="A bundled skill name is required.",
                success=False,
                error="Missing skill name",
            )

        handler = self._skill_handlers.get(skill_name.casefold())
        if handler is None:
            skill_definition = self._skill_catalog.get(skill_name)
            if skill_definition is None:
                available = ", ".join(self._list_available_skills()) or "none"
                return ToolResult(
                    content=(
                        f'Unknown bundled skill "{skill_name}". Available skills: {available}.'
                    ),
                    success=False,
                    error="Unknown skill",
                )
            return ToolResult(content=_render_skill_definition(skill_definition))

        outcome = handler()
        if inspect.isawaitable(outcome):
            return await outcome
        return outcome

    def _list_available_skills(self) -> tuple[str, ...]:
        """Return all available handler-backed and discovered skill names."""

        catalog_names = tuple(skill.name for skill in self._skill_catalog.list_skills())
        return tuple(sorted({*self._available_skills, *catalog_names}))


def _render_skill_definition(skill_definition: SkillDefinition) -> str:
    """Render one discovered skill as deterministic text for the model."""

    lines = [
        f"Skill: {skill_definition.name}",
        f"Source: {skill_definition.source_kind}",
    ]
    if skill_definition.description:
        lines.append(f"Description: {skill_definition.description}")
    if skill_definition.instructions:
        lines.extend(["Instructions:", skill_definition.instructions])
    return "\n".join(lines)


class SleepTool(Tool):
    """Pause execution for a validated number of seconds."""

    def __init__(
        self,
        sleeper: _SleepCallable | None = None,
        *,
        min_seconds: float = _DEFAULT_SLEEP_MIN_SECONDS,
        max_seconds: float = _DEFAULT_SLEEP_MAX_SECONDS,
    ) -> None:
        """Initialize the tool with injectable sleep behavior.

        Args:
            sleeper: Optional async callable used to perform the pause.
            min_seconds: Inclusive minimum allowed delay.
            max_seconds: Inclusive maximum allowed delay.
        """
        self._sleeper = sleeper or asyncio.sleep
        self._min_seconds = min_seconds
        self._max_seconds = max_seconds

    @property
    def name(self) -> str:
        """Return the unique tool identifier."""
        return "sleep"

    @property
    def description(self) -> str:
        """Return a human-readable tool description."""
        return "Pause execution for a bounded number of seconds."

    @property
    def parameters(self) -> dict[str, object]:
        """Return the JSON Schema for sleep parameters."""
        return _SLEEP_PARAMETERS

    @property
    def kind(self) -> ToolKind:
        """Return the tool kind used for confirmation policies."""
        return ToolKind.READ

    async def execute(self, **params: object) -> ToolResult:
        """Pause execution when the requested delay is within bounds.

        Args:
            **params: Tool parameters containing the required ``seconds`` value.

        Returns:
            A success result after sleeping, or a validation error.
        """
        seconds = _coerce_seconds(params.get("seconds"))
        if seconds is None:
            return ToolResult(
                content="Sleep requires a numeric seconds value.",
                success=False,
                error="Invalid seconds value",
            )
        if not self._min_seconds <= seconds <= self._max_seconds:
            return ToolResult(
                content=(
                    "Sleep seconds must be between "
                    f"{self._min_seconds:.1f} and {self._max_seconds:.1f} seconds."
                ),
                success=False,
                error="Seconds out of bounds",
            )

        await self._sleeper(seconds)
        return ToolResult(content=f"Slept for {seconds:g} seconds.")


WebSearchTool = DuckDuckGoSearchTool

__all__ = [
    "DuckDuckGoSearchTool",
    "SkillTool",
    "SleepTool",
    "ToolSearchTool",
    "WebSearchTool",
]
