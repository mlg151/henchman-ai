"""Pattern search tool - semantic and structural code search from natural language."""

from __future__ import annotations

import contextlib
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import ClassVar

from henchman.tools.base import Tool, ToolKind, ToolResult

_MAX_RESULTS = 200
_MAX_OUTPUT_CHARS = 50_000
_MAX_FILE_SIZE = 500_000  # bytes
_VALID_STRATEGIES = {"semantic", "structural", "combined"}


@dataclass
class PatternMatch:
    """A single pattern search match.

    Attributes:
        file: Path to the file containing the match.
        line: Line number of the match.
        context: The matching line content.
        score: Relevance score (higher = more relevant).
        matched_patterns: List of pattern labels that matched.
    """

    file: str
    line: int
    context: str
    score: int = 1
    matched_patterns: list[str] = field(default_factory=list)


@dataclass
class PatternSearchParams:
    """Parameters for pattern search."""
    description: str
    path: str
    top_k: int
    strategy: str


def _extract_keywords(description: str) -> list[str]:
    """Extract meaningful keywords from a natural language description.

    Filters out common English stop words and short tokens.

    Args:
        description: Natural language search description.

    Returns:
        List of meaningful keyword strings.
    """
    stop_words = {
        "a", "an", "the", "that", "this", "those", "these",
        "is", "are", "was", "were", "be", "been", "being",
        "have", "has", "had", "do", "does", "did",
        "in", "on", "at", "to", "for", "of", "with", "by",
        "and", "or", "but", "not", "from", "which", "all",
        "any", "some", "each", "every", "find", "look", "search",
        "show", "get", "return", "use", "using", "used",
        "code", "function", "class", "method", "module", "file",
        "where", "when", "what", "how", "who",
    }
    tokens = re.findall(r"[a-zA-Z_][a-zA-Z0-9_]*", description)
    return [t for t in tokens if len(t) >= 3 and t.lower() not in stop_words]  # noqa: PLR2004


def _extract_structural_patterns(description: str) -> list[tuple[str, str]]:
    """Extract structural code patterns from a description.

    Looks for language hints like "inherits from", "decorated with",
    "raises", "returns", etc. and builds regex patterns for them.

    Args:
        description: Natural language search description.

    Returns:
        List of (label, regex_pattern) tuples.
    """
    patterns: list[tuple[str, str]] = []
    desc_lower = description.lower()

    # Detect inheritance hints: "inherits from X", "subclass of X"
    for match in re.finditer(r"inherit(?:s)? from (\w+)|subclass of (\w+)", desc_lower):
        parent = match.group(1) or match.group(2)
        if parent:
            patterns.append((f"inherits:{parent}", rf"class\s+\w+\s*\([^)]*{parent}[^)]*\)"))

    # Detect decorator hints: "decorated with X", "@X"
    for match in re.finditer(r"@(\w+)|decorated with (\w+)|has decorator (\w+)", description):
        dec = match.group(1) or match.group(2) or match.group(3)
        if dec:
            patterns.append((f"decorator:@{dec}", rf"@{re.escape(dec)}"))

    # Detect async hint
    if re.search(r"\basync\b|\bawait\b|coroutine", desc_lower):
        patterns.append(("async_def", r"async\s+def\s+\w+"))

    # Detect exception handling
    if re.search(r"raise|exception|error handling", desc_lower):
        patterns.append(("raises", r"\braise\s+\w+"))

    # Detect class/function type hints
    if re.search(r"\bclass\b", desc_lower):
        patterns.append(("class_def", r"^class\s+\w+"))

    if re.search(r"\bfunction\b|\bmethod\b|\bdef\b", desc_lower):
        patterns.append(("function_def", r"(?:async\s+)?def\s+\w+"))

    # Detect typing/annotation usage
    if re.search(r"\btype hint\b|\bannotation\b|\btyped\b", desc_lower):
        patterns.append(("type_annotation", r":\s*[\w\[\], |]+\s*(?:=|->)"))

    return patterns


def _collect_files(root: Path, glob: str | None) -> list[Path]:
    """Collect files to search.

    Args:
        root: Root directory or file to search.
        glob: Optional glob pattern to filter files.

    Returns:
        List of file paths to search.
    """
    if root.is_file():
        return [root]
    if glob:
        return sorted(p for p in root.glob(glob) if p.is_file())
    return sorted(
        p for p in root.rglob("*")
        if p.is_file() and p.stat().st_size <= _MAX_FILE_SIZE
    )


def _search_file_structural(
    file_path: Path,
    keyword_patterns: list[tuple[str, re.Pattern[str]]],
    struct_patterns: list[tuple[str, re.Pattern[str]]],
) -> list[PatternMatch]:
    """Search a single file for keyword and structural patterns.

    Args:
        file_path: File to search.
        keyword_patterns: List of (label, compiled_regex) for keywords.
        struct_patterns: List of (label, compiled_regex) for structural patterns.

    Returns:
        List of PatternMatch objects found in the file.
    """
    try:
        lines = file_path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return []

    # Track matches per line: {line_num -> PatternMatch}
    line_matches: dict[int, PatternMatch] = {}

    for label, regex in keyword_patterns + struct_patterns:
        for i, line in enumerate(lines, 1):
            if regex.search(line):
                if i not in line_matches:
                    line_matches[i] = PatternMatch(
                        file=str(file_path),
                        line=i,
                        context=line.strip(),
                    )
                line_matches[i].score += 1
                line_matches[i].matched_patterns.append(label)

    return list(line_matches.values())


def _deduplicate_and_rank(matches: list[PatternMatch], top_k: int) -> list[PatternMatch]:
    """Sort matches by score descending, keeping the top_k results.

    Args:
        matches: All collected matches.
        top_k: Maximum number of results to return.

    Returns:
        Top-k matches sorted by score descending.
    """
    seen: set[tuple[str, int]] = set()
    unique: list[PatternMatch] = []
    for m in sorted(matches, key=lambda x: x.score, reverse=True):
        key = (m.file, m.line)
        if key not in seen:
            seen.add(key)
            unique.append(m)
        if len(unique) >= top_k:
            break
    return unique


def _build_pattern_search_report(
    description: str,
    matches: list[PatternMatch],
    strategy: str,
) -> str:
    """Build a formatted report of pattern search results.

    Args:
        description: The original natural language description.
        matches: Ranked list of matches.
        strategy: The strategy used ('semantic', 'structural', 'combined').

    Returns:
        Formatted Markdown report string.
    """
    if not matches:
        return f"No matches found for: {description}"

    lines: list[str] = [
        f"# Pattern Search: {description}",
        f"**Strategy:** {strategy} | **Results:** {len(matches)}\n",
    ]

    for m in matches:
        patterns_str = ", ".join(m.matched_patterns[:5]) if m.matched_patterns else "keyword"
        lines.append(f"### `{m.file}:{m.line}` (score: {m.score}, matched: {patterns_str})")
        lines.append(f"```\n{m.context}\n```")
        lines.append("")

    return "\n".join(lines)


def _execute_pattern_search(params: PatternSearchParams) -> ToolResult:
    """Execute the pattern search operation.

    Args:
        params: PatternSearchParams containing description, path, top_k, strategy.

    Returns:
        ToolResult with ranked matches report.
    """
    root = Path(params.path)
    if not root.exists():
        return ToolResult(
            content=f"Error: Path not found: {params.path}",
            success=False,
            error=f"Path not found: {params.path}",
        )

    if params.strategy not in _VALID_STRATEGIES:
        return ToolResult(
            content=f"Error: invalid strategy '{params.strategy}'. Valid: {sorted(_VALID_STRATEGIES)}",
            success=False,
            error=f"Invalid strategy: {params.strategy}",
        )

    files = _collect_files(root, None)

    keywords = _extract_keywords(params.description)
    struct_patterns = _extract_structural_patterns(params.description)

    # Compile keyword patterns
    kw_compiled: list[tuple[str, re.Pattern[str]]] = []
    if params.strategy in {"semantic", "combined"}:
        for kw in keywords:
            with contextlib.suppress(re.error):
                kw_compiled.append((f"kw:{kw}", re.compile(rf"\b{re.escape(kw)}\b", re.IGNORECASE)))

    struct_compiled: list[tuple[str, re.Pattern[str]]] = []
    if params.strategy in {"structural", "combined"}:
        for label, pat in struct_patterns:
            with contextlib.suppress(re.error):
                struct_compiled.append((label, re.compile(pat, re.MULTILINE)))

    if not kw_compiled and not struct_compiled:
        return ToolResult(
            content=f"Could not extract any searchable patterns from: {params.description}",
            success=True,
        )

    all_matches: list[PatternMatch] = []
    for file_path in files:
        file_matches = _search_file_structural(file_path, kw_compiled, struct_compiled)
        all_matches.extend(file_matches)

    ranked = _deduplicate_and_rank(all_matches, params.top_k)
    report = _build_pattern_search_report(params.description, ranked, params.strategy)

    # Truncate if needed
    if len(report) > _MAX_OUTPUT_CHARS:
        report = report[:_MAX_OUTPUT_CHARS] + "\n... (truncated)"

    return ToolResult(content=report, success=True)


class PatternSearchTool(Tool):
    """Search code using natural language descriptions.

    Accepts a natural language description of what to find, extracts
    structural heuristics (inheritance, decorators, async patterns, etc.)
    and keywords, then searches the codebase combining both approaches.
    Results are ranked by how many patterns match per location.

    Goes beyond exact regex (grep) by understanding structural code
    patterns described in plain English.
    """

    _parameters: ClassVar[dict[str, object]] = {
        "type": "object",
        "properties": {
            "description": {
                "type": "string",
                "description": (
                    "Natural language description of what to find, "
                    "e.g. 'functions that handle HTTP errors', "
                    "'classes that inherit from Tool'"
                ),
            },
            "path": {
                "type": "string",
                "description": "Root directory or file to search (defaults to current directory)",
                "default": ".",
            },
            "top_k": {
                "type": "integer",
                "description": "Maximum number of results to return",
                "default": 10,
            },
            "strategy": {
                "type": "string",
                "description": (
                    "Search strategy: 'semantic' (keyword-based), "
                    "'structural' (structural pattern extraction), "
                    "or 'combined' (both)"
                ),
                "enum": ["semantic", "structural", "combined"],
                "default": "combined",
            },
        },
        "required": ["description"],
    }

    @property
    def name(self: PatternSearchTool) -> str:
        """Tool name."""
        return "pattern_search"

    @property
    def description(self: PatternSearchTool) -> str:
        """Tool description."""
        return (
            "Search code using natural language descriptions. Extracts keywords and "
            "structural patterns (inheritance, decorators, async, etc.) from the description, "
            "then searches and ranks results. Use instead of crafting complex grep regexes."
        )

    @property
    def kind(self: PatternSearchTool) -> ToolKind:
        """Tool kind - READ is auto-approved."""
        return ToolKind.READ

    async def execute(  # type: ignore[override]
        self: PatternSearchTool,
        description: str = "",
        path: str = ".",
        top_k: int = 10,
        strategy: str = "combined",
        **kwargs: object,  # noqa: ARG002
    ) -> ToolResult:
        """Search code with a natural language description.

        Args:
            description: Natural language description of what to find.
            path: Root directory or file to search.
            top_k: Maximum number of results to return.
            strategy: Search strategy ('semantic', 'structural', 'combined').
            **kwargs: Additional arguments (ignored).

        Returns:
            ToolResult with ranked pattern search results.
        """
        if not description:
            return ToolResult(
                content="Error: description is required",
                success=False,
                error="description is required",
            )
        return _execute_pattern_search(
            PatternSearchParams(
                description=description,
                path=path,
                top_k=top_k,
                strategy=strategy
            )
        )
