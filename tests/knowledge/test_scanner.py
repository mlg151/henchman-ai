"""Tests for the knowledge graph code scanner."""

from pathlib import Path

import pytest

from henchman.knowledge.scanner import (
    _extract_imports,
    _extract_top_level_defs,
    _get_package_entities,
    _path_to_entity_id,
    _path_to_module,
    scan_repository,
)
from henchman.knowledge.store import KnowledgeStore

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def git_repo(tmp_path: Path) -> Path:
    """Create a minimal git repo with Python files."""
    import subprocess

    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)

    # Create a small package structure
    pkg = repo / "mylib"
    pkg.mkdir()
    (pkg / "__init__.py").write_text('"""My library."""\n')
    (pkg / "core.py").write_text(
        '"""Core module."""\n\nimport os\nfrom mylib import utils\n\n'
        'class Agent:\n    """The main agent."""\n    pass\n\n'
        'def run():\n    """Run the agent."""\n    pass\n'
    )
    (pkg / "utils.py").write_text(
        '"""Utility functions."""\n\nimport json\n\n'
        'def helper():\n    """Help with things."""\n    pass\n'
    )

    # Stage files so git ls-files sees them
    subprocess.run(["git", "add", "."], cwd=repo, check=True)
    return repo


@pytest.fixture
def store(git_repo: Path, tmp_path: Path) -> KnowledgeStore:
    """Store backed by a temp directory."""
    return KnowledgeStore(git_root=git_repo, base_dir=tmp_path / "kg")


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------


def test_path_to_entity_id() -> None:
    """Paths become slugified ids."""
    assert _path_to_entity_id("src/foo/bar.py") == "src-foo-bar-py"
    assert _path_to_entity_id("mylib/__init__.py") == "mylib---init---py"


def test_path_to_module() -> None:
    """Paths become dotted module strings."""
    assert _path_to_module("src/foo/bar.py") == "src.foo.bar"
    assert _path_to_module("mylib/core.py") == "mylib.core"


def test_extract_imports_simple() -> None:
    """Extract top-level imports."""
    source = "import os\nimport json\nfrom pathlib import Path\n"
    result = _extract_imports(source)
    assert "os" in result
    assert "json" in result
    assert "pathlib" in result


def test_extract_imports_from_style() -> None:
    """From-imports extract the root module."""
    source = "from henchman.core.agent import Agent\n"
    result = _extract_imports(source)
    assert "henchman" in result


def test_extract_imports_syntax_error() -> None:
    """Invalid Python returns empty list."""
    assert _extract_imports("def broken(") == []


def test_extract_imports_dedup() -> None:
    """Duplicate imports are deduplicated."""
    source = "import os\nimport os\n"
    result = _extract_imports(source)
    assert result.count("os") == 1


def test_extract_top_level_defs() -> None:
    """Extract classes and functions with docstrings."""
    source = (
        'class Foo:\n    """A foo."""\n    pass\n\n'
        'def bar():\n    """Do bar."""\n    pass\n\n'
        'async def baz():\n    pass\n'
    )
    defs = _extract_top_level_defs(source)
    assert len(defs) == 3

    kinds = [d[0] for d in defs]
    names = [d[1] for d in defs]
    assert "class" in kinds
    assert "function" in kinds
    assert "Foo" in names
    assert "bar" in names
    assert "baz" in names

    # Foo has docstring
    foo = [d for d in defs if d[1] == "Foo"][0]
    assert "A foo" in foo[2]

    # baz has no docstring
    baz = [d for d in defs if d[1] == "baz"][0]
    assert baz[2] == ""


def test_extract_top_level_defs_syntax_error() -> None:
    """Invalid Python returns empty list."""
    assert _extract_top_level_defs("class broken(") == []


def test_get_package_entities() -> None:
    """Package entities created from directory structure."""
    files = ["src/foo/bar.py", "src/foo/baz.py", "src/other/x.py"]
    packages = _get_package_entities(files)

    ids = set(packages.keys())
    assert "src" in ids
    assert "src-foo" in ids
    assert "src-other" in ids


# ---------------------------------------------------------------------------
# Full scan
# ---------------------------------------------------------------------------


def test_scan_repository_creates_entities(
    git_repo: Path, store: KnowledgeStore
) -> None:
    """Scanning creates file and package entities."""
    count = scan_repository(store, git_repo, incremental=False)
    assert count >= 2  # at least core.py and utils.py

    # File entities exist
    files = store.list_entities(entity_type="file")
    file_names = [e.name for e in files]
    assert any("core.py" in n for n in file_names)
    assert any("utils.py" in n for n in file_names)

    # Package entities exist
    pkgs = store.list_entities(entity_type="package")
    assert len(pkgs) >= 1


def test_scan_repository_creates_observations(
    git_repo: Path, store: KnowledgeStore
) -> None:
    """Scanning extracts class/function defs as observations."""
    scan_repository(store, git_repo, incremental=False)

    core = store.search_entities("core")
    assert len(core) >= 1
    core_entity = [e for e in core if "core" in (e.file_path or "")][0]
    obs_texts = [o.content for o in core_entity.observations]
    assert any("Agent" in t for t in obs_texts)
    assert any("run" in t for t in obs_texts)


def test_scan_repository_creates_relations(
    git_repo: Path, store: KnowledgeStore
) -> None:
    """Scanning creates import and contains relations."""
    scan_repository(store, git_repo, incremental=False)
    assert store.relation_count() > 0

    # core.py imports utils → there should be an imports edge
    core_id = _path_to_entity_id("mylib/core.py")
    relations = store.get_relations(core_id, direction="out")
    types = [r.relation_type for r in relations]
    assert "imports" in types


def test_scan_repository_incremental(
    git_repo: Path, store: KnowledgeStore
) -> None:
    """Incremental scan skips unchanged files."""
    count1 = scan_repository(store, git_repo, incremental=True)
    assert count1 >= 2

    # Second scan should skip all files
    count2 = scan_repository(store, git_repo, incremental=True)
    assert count2 == 0


def test_scan_repository_incremental_detects_changes(
    git_repo: Path, store: KnowledgeStore
) -> None:
    """Incremental scan detects modified files."""
    import subprocess

    scan_repository(store, git_repo, incremental=True)

    # Modify a file and stage it
    (git_repo / "mylib" / "utils.py").write_text(
        '"""Updated utils."""\n\ndef new_func():\n    pass\n'
    )
    subprocess.run(["git", "add", "."], cwd=git_repo, check=True)

    count = scan_repository(store, git_repo, incremental=True)
    assert count >= 1  # at least utils.py reprocessed


def test_scan_repository_updates_meta(
    git_repo: Path, store: KnowledgeStore
) -> None:
    """Scanning sets last_indexed and file_hashes in meta."""
    scan_repository(store, git_repo, incremental=True)
    assert store.meta.last_indexed != ""
    assert len(store.meta.file_hashes) > 0


def test_scan_empty_repo(tmp_path: Path) -> None:
    """Scanning a repo with no Python files returns 0."""
    import subprocess

    repo = tmp_path / "empty"
    repo.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    s = KnowledgeStore(git_root=repo, base_dir=tmp_path / "kg")
    assert scan_repository(s, repo) == 0
