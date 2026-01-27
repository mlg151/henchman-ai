"""List directory tool implementation."""

from pathlib import Path

from henchman.tools.base import Tool, ToolKind, ToolResult


class LsTool(Tool):
    """List directory contents.

    This tool lists the files and directories in a given path.
    """

    # Safety limits
    MAX_ITEMS = 1000

    @property
    def name(self) -> str:
        """Tool name."""
        return "ls"

    @property
    def description(self) -> str:
        """Tool description."""
        return "List files and directories in a path."

    @property
    def parameters(self) -> dict[str, object]:
        """JSON Schema for parameters."""
        return {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Path to list. Defaults to current directory.",
                    "default": ".",
                },
                "show_hidden": {
                    "type": "boolean",
                    "description": "Whether to show hidden files (starting with .)",
                    "default": False,
                },
            },
            "required": [],
        }

    @property
    def kind(self) -> ToolKind:
        """Tool kind - READ is auto-approved."""
        return ToolKind.READ

    async def execute(  # type: ignore[override]

        self,
        path: str = ".",
        show_hidden: bool = False,
        **kwargs: object,  # noqa: ARG002
    ) -> ToolResult:
        """List directory contents.

        Args:
            path: Path to list.
            show_hidden: Whether to show hidden files.
            **kwargs: Additional arguments (ignored).

        Returns:
            ToolResult with directory listing or error.
        """
        try:
            target = Path(path)

            if not target.exists():
                return ToolResult(
                    content=f"Error: Path not found: {path}",
                    success=False,
                    error=f"Path not found: {path}",
                )

            # If it's a file, just show the file
            if target.is_file():
                return ToolResult(
                    content=target.name,
                    success=True,
                )

            # List directory contents
            entries = []
            truncated = False

            # Use iterdir() which returns an iterator
            iterator = target.iterdir()
            # We can't sort immediately if we want to limit processing,
            # but for consistent output on small dirs, sorting is better.
            # So we collect up to limit + 1

            all_items = []
            try:
                for _ in range(self.MAX_ITEMS + 1):
                    all_items.append(next(iterator))
            except StopIteration:
                pass

            if len(all_items) > self.MAX_ITEMS:
                truncated = True
                all_items = all_items[:self.MAX_ITEMS]

            # Sort the collected items
            all_items.sort(key=lambda p: p.name)

            for item in all_items:
                # Skip hidden files unless requested
                if not show_hidden and item.name.startswith("."):
                    continue

                # Add suffix to indicate type
                if item.is_dir():
                    entries.append(f"{item.name}/")
                else:
                    entries.append(item.name)

            if truncated:
                entries.append(f"... Output truncated (limit reached: {self.MAX_ITEMS} items) ...")

            return ToolResult(
                content="\n".join(entries) if entries else "(empty directory)",
                success=True,
            )
        except PermissionError:
            return ToolResult(
                content=f"Error: Permission denied: {path}",
                success=False,
                error=f"Permission denied: {path}",
            )
        except Exception as e:  # pragma: no cover
            return ToolResult(
                content=f"Error listing directory: {e}",
                success=False,
                error=str(e),
            )
