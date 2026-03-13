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
        "async def baz():\n    pass\n"
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


def test_scan_repository_creates_entities(git_repo: Path, store: KnowledgeStore) -> None:
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


def test_scan_repository_creates_observations(git_repo: Path, store: KnowledgeStore) -> None:
    """Scanning extracts class/function defs as observations."""
    scan_repository(store, git_repo, incremental=False)

    core = store.search_entities("core")
    assert len(core) >= 1
    core_entity = [e for e in core if "core" in (e.file_path or "")][0]
    obs_texts = [o.content for o in core_entity.observations]
    assert any("Agent" in t for t in obs_texts)
    assert any("run" in t for t in obs_texts)


def test_scan_repository_creates_relations(git_repo: Path, store: KnowledgeStore) -> None:
    """Scanning creates import and contains relations."""
    scan_repository(store, git_repo, incremental=False)
    assert store.relation_count() > 0

    # core.py imports utils → there should be an imports edge
    core_id = _path_to_entity_id("mylib/core.py")
    relations = store.get_relations(core_id, direction="out")
    types = [r.relation_type for r in relations]
    assert "imports" in types


def test_scan_repository_incremental(git_repo: Path, store: KnowledgeStore) -> None:
    """Incremental scan skips unchanged files."""
    count1 = scan_repository(store, git_repo, incremental=True)
    assert count1 >= 2

    # Second scan should skip all files
    count2 = scan_repository(store, git_repo, incremental=True)
    assert count2 == 0


def test_scan_repository_incremental_detects_changes(git_repo: Path, store: KnowledgeStore) -> None:
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


def test_scan_repository_updates_meta(git_repo: Path, store: KnowledgeStore) -> None:
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


def test_get_git_tracked_python_files_error_handling(tmp_path: Path) -> None:
    """Test error handling in _get_git_tracked_python_files."""

    from henchman.knowledge.scanner import _get_git_tracked_python_files

    # Test with non-git directory (git command will fail)
    result = _get_git_tracked_python_files(tmp_path)
    assert result == [], "Should return empty list when git command fails"

    # Also test when subprocess.run raises an exception
    # We can't easily test this without mocking, but the code has try/except
    # that catches subprocess.SubprocessError and FileNotFoundError

    print("✓ _get_git_tracked_python_files error handling test passed")


def test_build_module_lookup_edge_cases() -> None:
    """Test edge cases in _build_module_lookup."""
    from henchman.knowledge.scanner import (
        _build_module_lookup,
        _path_to_entity_id,
    )

    # Test: module takes precedence over package (package_name already in module_to_eid)
    # Put foo.py first so it gets processed before foo/__init__.py
    python_files = [
        "foo.py",              # Module foo - priority 1
        "foo/__init__.py",     # Package foo - priority 0 but comes second in list
    ]

    module_to_eid, _ = _build_module_lookup(python_files)

    # foo.py should win because it's processed first (even though __init__.py has priority 0,
    # they're sorted by priority then module name, so __init__.py comes first)
    # Actually, wait: __init__.py has priority 0, foo.py has priority 1
    # So __init__.py comes first in sorted list
    # But foo.py maps "foo" when it processes
    # So when __init__.py tries to map "foo", it's already mapped
    # This tests the "if package_name not in module_to_eid:" False branch
    assert module_to_eid["foo"] == _path_to_entity_id("foo.py")

    # Test: __init__ files don't create last_part mappings
    python_files2 = [
        "foo/__init__.py",
    ]

    module_to_eid2, _ = _build_module_lookup(python_files2)

    # "__init__" should not be mapped as last_part
    assert "__init__" not in module_to_eid2

    # Test: last_part already in module_to_eid (should not overwrite)
    python_files3 = [
        "x/y/z.py",    # Maps "z" -> x-y-z-py
        "a/b/z.py",    # Should not overwrite "z" mapping
    ]

    module_to_eid3, _ = _build_module_lookup(python_files3)

    # "z" should map to first file (a/b/z.py comes first alphabetically)
    assert module_to_eid3["z"] == _path_to_entity_id("a/b/z.py")

    print("✓ _build_module_lookup edge cases test passed")


def test_import_resolution_bug() -> None:
    """Test the import resolution bug fix.
    
    The bug: When importing "foo", the scanner should prefer foo/__init__.py
    over foo/bar.py or foo/baz.py when multiple files could satisfy the import.
    """
    from henchman.knowledge.scanner import (
        _build_module_lookup,
        _find_import_target_optimized,
        _path_to_entity_id,
        _path_to_module,
    )

    # Create test files that demonstrate the bug
    python_files = [
        "foo/__init__.py",      # Package foo - should be first choice
        "foo/bar.py",           # Submodule - should be second choice
        "foo/baz.py",           # Another submodule - third choice
        "other/foo.py",         # Different foo module in different package
    ]

    module_to_eid, eid_to_module = _build_module_lookup(python_files)

    # Test 1: External file importing "foo" should find foo/__init__.py
    # (not foo/bar.py or foo/baz.py arbitrarily)
    mod = "foo"
    importing_eid = _path_to_entity_id("external.py")
    importing_module = None  # External file not in repo

    result = _find_import_target_optimized(
        mod, importing_eid, importing_module, module_to_eid
    )

    expected = _path_to_entity_id("foo/__init__.py")
    assert result == expected, (
        f"Importing '{mod}' should find foo/__init__.py, got {result}"
    )

    # Test 2: foo/bar.py importing "foo" should find foo/__init__.py
    # (not foo.py or other/foo.py)
    mod = "foo"
    importing_eid = _path_to_entity_id("foo/bar.py")
    importing_module = _path_to_module("foo/bar.py")

    result = _find_import_target_optimized(
        mod, importing_eid, importing_module, module_to_eid
    )

    expected = _path_to_entity_id("foo/__init__.py")
    assert result == expected, (
        f"foo/bar.py importing '{mod}' should find foo/__init__.py, got {result}"
    )

    # Test 3: Self-import detection
    # foo/__init__.py importing "foo" should be None (self-import)
    mod = "foo"
    importing_eid = _path_to_entity_id("foo/__init__.py")
    importing_module = _path_to_module("foo/__init__.py")

    result = _find_import_target_optimized(
        mod, importing_eid, importing_module, module_to_eid
    )

    assert result is None, (
        f"foo/__init__.py importing '{mod}' should be self-import (None), got {result}"
    )

    # Test 4: Module takes precedence over package when both exist
    python_files2 = [
        "foo.py",              # Module foo
        "foo/__init__.py",     # Package foo
    ]

    module_to_eid2, eid_to_module2 = _build_module_lookup(python_files2)

    mod = "foo"
    importing_eid = _path_to_entity_id("external.py")
    importing_module = None

    result = _find_import_target_optimized(
        mod, importing_eid, importing_module, module_to_eid2
    )

    expected = _path_to_entity_id("foo.py")
    assert result == expected, (
        f"Module foo.py should take precedence over package foo/__init__.py, got {result}"
    )

    # Test 5: Edge cases in _build_module_lookup
    # Test that __init__ files don't create last_part mappings
    python_files3 = [
        "foo/__init__.py",
        "bar/__init__.py",
    ]

    module_to_eid3, eid_to_module3 = _build_module_lookup(python_files3)

    # "__init__" should not be in the lookup as a last_part
    assert "__init__" not in module_to_eid3, "__init__ should not be mapped as last_part"

    # But package names should be mapped
    assert "foo" in module_to_eid3, "Package foo should be mapped"
    assert "bar" in module_to_eid3, "Package bar should be mapped"

    # Test 6: Test that last_part mapping respects existing mappings
    python_files4 = [
        "x/y/z.py",    # module x.y.z, last_part = "z"
        "a/b/z.py",    # module a.b.z, last_part = "z" (should not overwrite)
    ]

    module_to_eid4, _ = _build_module_lookup(python_files4)

    # Files are sorted by module name, so a.b.z comes before x.y.z
    # Therefore "z" should map to a/b/z.py
    assert module_to_eid4["z"] == _path_to_entity_id("a/b/z.py")

    # And x.y.z should have its full module name mapped
    assert module_to_eid4["x.y.z"] == _path_to_entity_id("x/y/z.py")
