"""Live tool scopes with explicit role boundaries and independent discovery."""

from __future__ import annotations

from henchman.tools.base import Tool
from henchman.tools.registry import ToolRegistry


class ScopedToolRegistry(ToolRegistry):
    """Resolve allowed parent tools live, with local overrides and exclusions."""

    def __init__(
        self,
        parent: ToolRegistry,
        allowed_tools: list[str],
        *,
        inherit_auto_approve: bool = False,
    ) -> None:
        super().__init__(retry_config=parent._retry_config)
        self._parent = parent
        self._allowed_tools = tuple(dict.fromkeys(allowed_tools))
        self._excluded_tools: set[str] = set()
        self._inherit_auto_approve = inherit_auto_approve
        self._search_source: Tool | None = None
        self._scoped_search: Tool | None = None
        self.inherit_policies_from(parent)

    def register(self, tool: Tool) -> None:
        """Add a local tool, overriding any inherited entry of the same name."""
        super().register(tool)
        self._excluded_tools.discard(tool.name)

    def unregister(self, name: str) -> None:
        """Hide a tool, including future parent registrations, until re-registered."""
        super().unregister(name)
        self._excluded_tools.add(name)
        if name == "tool_search":
            self._search_for_scope(None)

    def get(self, name: str) -> Tool | None:
        """Resolve a local override or a currently allowed parent tool."""
        tool = self._tools.get(name)
        if (
            tool is None
            and name not in self._excluded_tools
            and name in self._allowed_tools
        ):
            tool = self._parent.get(name)
        return self._search_for_scope(tool) if name == "tool_search" else tool

    def list_tools(self) -> list[str]:
        """List current allowed and local names once, in stable scope order."""
        names = dict.fromkeys((*self._allowed_tools, *self._tools))
        return [name for name in names if self.get(name) is not None]

    @property
    def discovered_tools(self) -> list[str]:
        """Refresh the search binding before returning its current priorities."""
        self.get("tool_search")
        return super().discovered_tools

    def is_auto_approved(self, name: str) -> bool:
        """Honor local approvals and optionally the parent's current approvals."""
        return super().is_auto_approved(name) or (
            self._inherit_auto_approve and self._parent.is_auto_approved(name)
        )

    def _search_for_scope(self, source: Tool | None) -> Tool | None:
        """Cache a scope-bound builtin search until its source identity changes."""
        if source is self._search_source:
            return self._scoped_search

        from henchman.tools.builtins.tier1_tools import ToolSearchTool

        self._search_source = source
        self._discovery_tool = None
        self._discovered_tools = []
        self._scoped_search = (
            source.for_registry(self) if isinstance(source, ToolSearchTool) else source
        )
        return self._scoped_search
