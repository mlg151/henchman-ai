"""Fresh bounded Python definitions, static relationships and scoped guidance."""

from __future__ import annotations

import ast
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from henchman.analysis.repository_evidence import (
    bounded_result,
    evidence_id,
    source_record,
    unavailable,
)
from henchman.analysis.repository_sources import (
    MAX_ENTRIES,
    MAX_FILE_BYTES,
    MAX_FILES,
    MAX_SOURCE_BYTES,
    TOTAL_SECONDS,
    RepositoryObservation,
    repository_target,
)
from henchman.analysis.smells.symbols import iter_functions
from henchman.config.context import (
    DEFAULT_FILENAMES,
    ContextSnapshot,
    repository_instruction_candidates,
)
from henchman.rag.evidence import EvidenceUnavailable, SourceSnapshot, WorkspaceBinding
from henchman.tools.access_policy import ToolAccessError
from henchman.tools.base import ToolResult

MAX_AST_NODES = 50_000
MAX_TOTAL_AST_NODES = 200_000
MAX_DEFINITIONS = 2048
MAX_RELATED = 40
MAX_INSTRUCTIONS = 8


@dataclass
class ParsedSource:
    source: SourceSnapshot
    tracked: bool
    tree: ast.Module

    @property
    def is_test(self) -> bool:
        path = Path(self.source.relative_path)
        return "tests" in path.parts or path.name.startswith("test_") or path.name.endswith("_test.py")


async def _definitions(parsed: ParsedSource, keywords: set[str], revision: str | None,
                       observation: RepositoryObservation, limit: int) -> tuple[list[dict[str, Any]], bool]:
    matches: list[dict[str, Any]] = []
    for index, (symbol, node) in enumerate(iter_functions(parsed.tree)):
        if index % 32 == 0:
            await observation.checkpoint()
        doc = ast.get_docstring(node, clean=False) or ""
        text = f"{symbol.replace('_', ' ')} {doc[:4096]}".casefold()
        matched = sorted(word for word in keywords if word in text)
        if not matched:
            continue
        if len(matches) >= limit:
            return matches, True
        record = source_record(parsed.source, start=node.lineno, end=node.end_lineno or node.lineno,
                               revision=revision, tracked=parsed.tracked)
        record.update(id=evidence_id(parsed.source.relative_path, symbol, node.lineno),
                      symbol=symbol, retrieval_reasons=[f"definition_keyword:{word}" for word in matched],
                      score=len(matched))
        matches.append(record)
    return matches, False


def _relationships(parsed: ParsedSource, implementations: list[dict[str, Any]],
                   revision: str | None) -> list[dict[str, Any]]:
    """Static name/import candidates, explicitly not resolved runtime call edges."""
    names: dict[str, set[str]] = {}
    for item in implementations:
        names.setdefault(item["symbol"].rsplit(".", 1)[-1], set()).add(item["id"])
    aliases: dict[str, set[str]] = {}
    for node in ast.walk(parsed.tree):
        if isinstance(node, ast.ImportFrom):
            for alias in node.names:
                if alias.name in names:
                    aliases[alias.asname or alias.name] = names[alias.name]
    names.update(aliases)
    records: list[dict[str, Any]] = []
    seen: set[int] = set()
    for node in ast.walk(parsed.tree):
        name: str | None = None
        if isinstance(node, ast.Name):
            name = node.id
        elif isinstance(node, ast.Attribute):
            name = node.attr
        if name not in names or not isinstance(node, (ast.Name, ast.Attribute)) or node.lineno in seen:
            continue
        seen.add(node.lineno)
        record = source_record(parsed.source, start=node.lineno,
                               end=node.end_lineno or node.lineno,
                               revision=revision, tracked=parsed.tracked)
        record.update(applies_to=sorted(names[name]), retrieval_reasons=["static_name_reference"],
                      relationship="candidate_only")
        records.append(record)
        if len(records) > MAX_RELATED:
            break
    return records


async def search_repository(
    binding: WorkspaceBinding, *, description: str, path: str, top_k: int,
    instruction_snapshot: ContextSnapshot | None = None,
) -> ToolResult:
    """Observe current bytes, serialize bounded evidence, then requalify publication."""
    from henchman.tools.builtins.pattern_search import _extract_keywords

    observation = RepositoryObservation(binding, time.monotonic() + TOTAL_SECONDS)
    diagnostics: list[dict[str, str]] = []
    sources: list[SourceSnapshot] = []
    parsed_sources: list[ParsedSource] = []
    pack: dict[str, Any] = {
        "version": 1, "kind": "repository_evidence", "status": "complete", "complete": True,
        "task_verified": False, "implementations": [], "tests": [], "references": [],
        "instructions": [], "diagnostics": diagnostics,
        "limits": {"files": MAX_FILES, "entries": MAX_ENTRIES, "file_bytes": MAX_FILE_BYTES,
                   "source_bytes": MAX_SOURCE_BYTES, "instruction_sources": MAX_INSTRUCTIONS,
                   "matched_definitions": MAX_DEFINITIONS, "related_items_per_kind": MAX_RELATED,
                   "ast_nodes_per_file": MAX_AST_NODES, "ast_nodes_total": MAX_TOTAL_AST_NODES,
                   "seconds": TOTAL_SECONDS},
        "limitations": ["Python functions and methods only; lexical keyword ranking",
                        "Static references are candidates, not runtime call resolution",
                        "No atomic filesystem snapshot, execution or task verification",
                        "Instructions are scoped untrusted evidence, not activated guidance"],
    }
    try:
        await observation.checkpoint()
        target = repository_target(binding, path)
        workspace = await observation.start()
        membership = await observation.candidates(target)
        if len(membership) > MAX_FILES:
            diagnostics.append({"code": "repository_file_budget_exceeded"})
        total_nodes = 0
        for relative, tracked in membership[:MAX_FILES]:
            await observation.checkpoint()
            try:
                source = observation.source(relative)
            except (EvidenceUnavailable, OSError) as exc:
                code = str(exc) if isinstance(exc, EvidenceUnavailable) else "source_read_unavailable"
                diagnostics.append({"code": code, "path": relative})
                continue
            sources.append(source)
            try:
                tree = ast.parse(source.text, filename="<repository source>")
            except (SyntaxError, ValueError, RecursionError):
                diagnostics.append({"code": "python_parse_error", "path": relative})
                continue
            count = 0
            for _node in ast.walk(tree):
                count += 1
                if count > MAX_AST_NODES or total_nodes + count > MAX_TOTAL_AST_NODES:
                    break
            exceeded = count > MAX_AST_NODES or total_nodes + count > MAX_TOTAL_AST_NODES
            total_nodes += count
            if exceeded:
                diagnostics.append({"code": "python_ast_budget_exceeded", "path": relative})
                continue
            parsed_sources.append(ParsedSource(source, tracked, tree))
        keywords = {word.casefold() for word in _extract_keywords(description)}
        matches: list[dict[str, Any]] = []
        for parsed in parsed_sources:
            await observation.checkpoint()
            if not parsed.is_test:
                definitions, exceeded = await _definitions(
                    parsed, keywords, workspace.revision, observation, MAX_DEFINITIONS - len(matches),
                )
                matches.extend(definitions)
                if exceeded:
                    diagnostics.append({"code": "definition_budget_exceeded"})
                    break
        matches.sort(key=lambda item: (-item["score"], item["path"], item["start_line"]))
        pack["implementations"] = matches[:top_k]
        if not keywords:
            diagnostics.append({"code": "query_has_no_searchable_keywords"})
        for parsed in parsed_sources:
            await observation.checkpoint()
            field = "tests" if parsed.is_test else "references"
            records = _relationships(parsed, pack["implementations"], workspace.revision)
            pack[field].extend(records)
            if len(pack[field]) > MAX_RELATED:
                pack[field] = pack[field][:MAX_RELATED]
                if not any(item["code"] == "related_item_budget_exceeded" for item in diagnostics):
                    diagnostics.append({"code": "related_item_budget_exceeded"})

        filenames = DEFAULT_FILENAMES
        if instruction_snapshot is not None and instruction_snapshot.discovery is not None:
            filenames = instruction_snapshot.discovery.filenames
        discovery: dict[str, tuple[tuple[Path, Path], ...]] = {}
        instruction_records: dict[str, dict[str, Any]] = {}
        for implementation in pack["implementations"]:
            await observation.checkpoint()
            candidates = repository_instruction_candidates(binding.root, binding.root / implementation["path"], filenames)
            discovery[implementation["path"]] = candidates
            for candidate, scope in candidates:
                relative = candidate.relative_to(binding.root).as_posix()
                if relative in instruction_records:
                    instruction_records[relative]["applies_to"].append(implementation["id"])
                    continue
                if len(instruction_records) >= MAX_INSTRUCTIONS:
                    if not any(item["code"] == "instruction_budget_exceeded" for item in diagnostics):
                        diagnostics.append({"code": "instruction_budget_exceeded"})
                    continue
                await observation.checkpoint()
                try:
                    source = observation.source(relative, max_bytes=32 * 1024)
                except (EvidenceUnavailable, OSError):
                    diagnostics.append({"code": "instruction_source_unavailable", "path": relative})
                    continue
                sources.append(source)
                record = source_record(source, start=1, end=max(1, len(source.text.splitlines())),
                                       revision=workspace.revision, tracked=False)
                # Instruction discovery is not a Git membership assertion.
                # Only Python candidates carry the captured tracked/untracked bit.
                record.pop("tracked")
                if instruction_snapshot is not None and instruction_snapshot.discovery is not None:
                    limit = instruction_snapshot.discovery.max_source_chars
                    if limit is not None and len(record["content"]) > limit:
                        record["content"] = record["content"][:max(0, limit)]
                        record["excerpt_truncated"] = True
                record.update(scope=scope.relative_to(binding.root).as_posix(),
                              applies_to=[implementation["id"]], kind="repository_instruction",
                              membership="scoped_instruction_discovery",
                              order=len(instruction_records), authority="untrusted_scoped_evidence")
                instruction_records[relative] = record
        pack["instructions"] = list(instruction_records.values())
        pack["coverage"] = {"candidate_files": len(membership), "observed_files": len(parsed_sources),
                            "source_bytes": observation.consumed, "matching_definitions": len(matches),
                            "excluded": ["non-Python paths", "ignored paths", "nested repositories"]}
        pack["repository_id"] = binding.repository_id
        pack["current_revision"] = workspace.revision
        pack["complete"] = not diagnostics
        result = bounded_result(pack)
        await observation.verify(sources, target, membership)
        for relative, candidates in discovery.items():
            await observation.checkpoint()
            if repository_instruction_candidates(binding.root, binding.root / relative, filenames) != candidates:
                raise EvidenceUnavailable("instruction_discovery_changed")
        await observation.checkpoint()
        return result
    except ToolAccessError:
        return unavailable("repository_authorization_changed")
    except EvidenceUnavailable as exc:
        return unavailable(str(exc))
    except (OSError, ValueError, RecursionError):
        return unavailable("repository_observation_unavailable")
