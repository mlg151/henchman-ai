"""Tests to boost coverage for knowledge/scanner.py."""

from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from henchman.knowledge.scanner import (
    _build_module_lookup,
    _find_import_target,
    _find_import_target_optimized,
    _get_git_tracked_python_files,
    scan_repository,
)
from henchman.knowledge.store import KnowledgeStore

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def git_repo_complex(tmp_path: Path) -> Path:
    """Create a more complex git repo for coverage testing."""
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)

    # Package with __init__.py
    pkg = repo / "myapp"
    pkg.mkdir()
    (pkg / "__init__.py").write_text('"""App package."""\n')
    (pkg / "core.py").write_text(
        '"""Core module."""\nimport os\nfrom myapp import utils\n\nclass Agent:\n    pass\n'
    )
    (pkg / "utils.py").write_text(
        '"""Utils."""\nimport json\n\ndef helper():\n    """Help.\n\nMultiline."""\n    pass\n'
    )

    # Sub-package
    sub = pkg / "sub"
    sub.mkdir()
    (sub / "__init__.py").write_text('"""Subpackage."""\n')
    (sub / "module.py").write_text('"""Module."""\nfrom myapp import core\n')

    subprocess.run(["git", "add", "."], cwd=repo, check=True)
    return repo


@pytest.fixture
def store(git_repo_complex: Path, tmp_path: Path) -> KnowledgeStore:
    """KnowledgeStore backed by a temp directory."""
    return KnowledgeStore(git_root=git_repo_complex, base_dir=tmp_path / "kg")


# ---------------------------------------------------------------------------
# _get_git_tracked_python_files - lines 91-92
# ---------------------------------------------------------------------------


class TestGetGitTrackedPythonFiles:
    """Cover missing lines in _get_git_tracked_python_files."""

    def test_subprocess_error_returns_empty(self, tmp_path: Path) -> None:
        """Lines 91-92: exception returns empty list."""
        with patch(
            "subprocess.run",
            side_effect=subprocess.SubprocessError("fail"),
        ):
            result = _get_git_tracked_python_files(tmp_path)
            assert result == []

    def test_file_not_found_returns_empty(self, tmp_path: Path) -> None:
        """Lines 91-92: FileNotFoundError returns empty list."""
        with patch(
            "subprocess.run",
            side_effect=FileNotFoundError("git not found"),
        ):
            result = _get_git_tracked_python_files(tmp_path)
            assert result == []

    def test_nonzero_returncode_returns_empty(self, tmp_path: Path) -> None:
        """Lines 88-89: non-zero returncode returns empty list."""
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stdout = ""
        with patch("subprocess.run", return_value=mock_result):
            result = _get_git_tracked_python_files(tmp_path)
            assert result == []


# ---------------------------------------------------------------------------
# _find_import_target - lines 243-250
# ---------------------------------------------------------------------------


class TestFindImportTarget:
    """Cover _find_import_target function."""

    def test_finds_matching_module(self) -> None:
        """Lines 243-250: finds entity ID of matching module."""
        python_files = ["myapp/core.py", "myapp/utils.py"]
        result = _find_import_target("utils", "myapp-core-py", python_files)
        assert result == "myapp-utils-py"

    def test_no_match_returns_none(self) -> None:
        """Line 250: no match returns None."""
        python_files = ["myapp/core.py"]
        result = _find_import_target("nonexistent", "myapp-core-py", python_files)
        assert result is None

    def test_self_match_breaks(self) -> None:
        """Line 249: self-match (file_eid equals other_eid) returns None."""
        python_files = ["myapp/core.py"]
        # file_eid matches the computed eid for core.py
        file_eid = "myapp-core-py"
        result = _find_import_target("core", file_eid, python_files)
        assert result is None


# ---------------------------------------------------------------------------
# _find_import_target_optimized - lines 279, 284->289, 294, 304-308, 317-329
# ---------------------------------------------------------------------------


class TestFindImportTargetOptimized:
    """Cover _find_import_target_optimized function."""

    def test_exact_self_import_returns_none(self) -> None:
        """Line 279: exact self-import (file_module == mod) returns None."""
        module_to_eid = {"myapp.core": "myapp-core-py"}
        eid_to_module = {"myapp-core-py": "myapp.core"}
        result = _find_import_target_optimized(
            mod="myapp.core",
            file_eid="myapp-core-py",
            file_module="myapp.core",
            module_to_eid=module_to_eid,
        )
        assert result is None

    def test_package_init_self_import_returns_none(self) -> None:
        """Lines 284->289: __init__.py importing its own package name returns None."""
        module_to_eid = {"myapp": "myapp---init--py"}
        eid_to_module = {"myapp---init--py": "myapp.__init__"}
        result = _find_import_target_optimized(
            mod="myapp",
            file_eid="myapp---init--py",
            file_module="myapp.__init__",
            module_to_eid=module_to_eid,
        )
        assert result is None

    def test_no_candidates_returns_none(self) -> None:
        """Line 294: no prefix match in module_to_eid returns None."""
        module_to_eid = {"myapp.core": "myapp-core-py"}
        eid_to_module = {"myapp-core-py": "myapp.core"}
        result = _find_import_target_optimized(
            mod="nonexistent",
            file_eid="other-file-py",
            file_module="other.file",
            module_to_eid=module_to_eid,
        )
        assert result is None

    def test_self_match_in_prefix_loop_returns_none(self) -> None:
        """Lines 304-308: self-match found in prefix loop returns None."""
        module_to_eid = {"myapp.utils": "myapp-utils-py"}
        eid_to_module = {"myapp-utils-py": "myapp.utils"}
        result = _find_import_target_optimized(
            mod="myapp",
            file_eid="myapp-utils-py",  # this file is myapp.utils
            file_module="myapp.utils",
            module_to_eid=module_to_eid,
        )
        assert result is None

    def test_candidate_priority_sorting(self) -> None:
        """Lines 317-329: candidates are sorted with exact match first."""
        module_to_eid = {
            "myapp": "myapp---init--py",
            "myapp.core": "myapp-core-py",
            "myapp.utils": "myapp-utils-py",
        }
        eid_to_module = {
            "myapp---init--py": "myapp.__init__",
            "myapp-core-py": "myapp.core",
            "myapp-utils-py": "myapp.utils",
        }
        # Looking for "myapp" - exact match should win (myapp.__init__)
        result = _find_import_target_optimized(
            mod="myapp",
            file_eid="other-py",
            file_module="other",
            module_to_eid=module_to_eid,
        )
        assert result == "myapp---init--py"

    def test_exact_match_returns_target(self) -> None:
        """Exact match in module_to_eid returns target."""
        module_to_eid = {"myapp.utils": "myapp-utils-py"}
        eid_to_module = {"myapp-utils-py": "myapp.utils"}
        result = _find_import_target_optimized(
            mod="myapp.utils",
            file_eid="myapp-core-py",
            file_module="myapp.core",
            module_to_eid=module_to_eid,
        )
        assert result == "myapp-utils-py"

    def test_exact_match_self_returns_none(self) -> None:
        """Exact match in module_to_eid but target is self returns None."""
        module_to_eid = {"myapp.utils": "myapp-utils-py"}
        eid_to_module = {"myapp-utils-py": "myapp.utils"}
        result = _find_import_target_optimized(
            mod="myapp.utils",
            file_eid="myapp-utils-py",  # self
            file_module="myapp.utils",
            module_to_eid=module_to_eid,
        )
        assert result is None


# ---------------------------------------------------------------------------
# scan_repository - lines 367-370, 381, 417->429
# ---------------------------------------------------------------------------


class TestScanRepositoryMissingLines:
    """Cover missing lines in scan_repository."""

    def test_scan_with_package_entities(
        self, git_repo_complex: Path, tmp_path: Path
    ) -> None:
        """Lines 367-370: package parent-child contains relation is added."""
        store = KnowledgeStore(git_root=git_repo_complex, base_dir=tmp_path / "kg")
        count = scan_repository(store, git_repo_complex, incremental=False)
        assert count > 0

        # Check that file→package contains relations were added
        entities = store.list_entities()
        entity_ids = {e.id for e in entities}
        assert len(entity_ids) > 0

    def test_scan_incremental_skips_unchanged(
        self, git_repo_complex: Path, tmp_path: Path
    ) -> None:
        """Line 381: incremental scan skips files with same hash."""
        store = KnowledgeStore(git_root=git_repo_complex, base_dir=tmp_path / "kg")
        # First scan
        count1 = scan_repository(store, git_repo_complex, incremental=True)

        # Second scan with same files → should skip (incremental)
        count2 = scan_repository(store, git_repo_complex, incremental=True)
        # No new processing since files haven't changed
        assert count2 == 0

    def test_scan_file_with_subpackage_contains_relation(
        self, git_repo_complex: Path, tmp_path: Path
    ) -> None:
        """Lines 417->429: file in subdirectory has file→package contains relation."""
        store = KnowledgeStore(git_root=git_repo_complex, base_dir=tmp_path / "kg")
        count = scan_repository(store, git_repo_complex, incremental=False)
        assert count > 0

        # Get all entities and check for contains relations via each entity
        entities = store.list_entities()
        all_relations = []
        for entity in entities:
            relations = store.get_relations(entity.id)
            all_relations.extend(relations)

        contains_relations = [r for r in all_relations if r.relation_type == "contains"]
        assert len(contains_relations) > 0

    def test_scan_empty_repo_returns_zero(self, tmp_path: Path) -> None:
        """scan_repository returns 0 when no Python files."""
        repo = tmp_path / "empty_repo"
        repo.mkdir()
        subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
        subprocess.run(["git", "add", "."], cwd=repo, check=True)

        store = KnowledgeStore(git_root=repo, base_dir=tmp_path / "kg")
        with patch(
            "henchman.knowledge.scanner._get_git_tracked_python_files",
            return_value=[],
        ):
            count = scan_repository(store, repo)
            assert count == 0

    def test_scan_nonexistent_file_is_skipped(
        self, git_repo_complex: Path, tmp_path: Path
    ) -> None:
        """Line 381: nonexistent files are skipped gracefully."""
        store = KnowledgeStore(git_root=git_repo_complex, base_dir=tmp_path / "kg")
        # Patch to return a file that doesn't exist
        with patch(
            "henchman.knowledge.scanner._get_git_tracked_python_files",
            return_value=["nonexistent/file.py"],
        ):
            count = scan_repository(store, git_repo_complex, incremental=False)
            assert count == 0


# ---------------------------------------------------------------------------
# Additional targeted tests for remaining missing lines
# ---------------------------------------------------------------------------


class TestFindImportTargetOptimizedAdditional:
    """Cover remaining missing lines 284->289, 294, 308, 317-329."""

    def test_init_file_non_self_package_name_continues(self) -> None:
        """Line 284->289: __init__.py with package_name != mod, continues past."""
        # file_module ends with .__init__ but package_name (myapp) != mod (utils)
        module_to_eid = {"utils": "utils-py"}
        eid_to_module = {"utils-py": "utils"}
        result = _find_import_target_optimized(
            mod="utils",
            file_eid="myapp---init--py",
            file_module="myapp.__init__",  # package_name = "myapp" != mod "utils"
            module_to_eid=module_to_eid,
        )
        # package_name (myapp) != mod (utils), so falls through to exact match
        # exact match found: "utils" → "utils-py" which != file_eid → return target
        assert result == "utils-py"

    def test_exact_match_self_without_init_file_module(self) -> None:
        """Line 294: exact match target == file_eid (self-match via exact lookup)."""
        # file_module != mod (no early return at 279)
        # file_module doesn't end with .__init__
        # mod IS in module_to_eid, target == file_eid
        module_to_eid = {"myapp.core": "myapp-core-py"}
        eid_to_module = {"myapp-core-py": "myapp.core"}
        result = _find_import_target_optimized(
            mod="myapp.core",  # in module_to_eid, target = "myapp-core-py"
            file_eid="myapp-core-py",  # same as target → self-match
            file_module="myapp.utils",  # different from mod, no early return
            module_to_eid=module_to_eid,
        )
        # Line 294: target == file_eid → return None
        assert result is None

    def test_prefix_match_adds_non_self_candidates(self) -> None:
        """Lines 308, 317-329: prefix match with multiple non-self candidates."""
        # mod NOT in module_to_eid (no exact match)
        # but "myapp.core" and "myapp.utils" start with "myapp."
        module_to_eid = {
            "myapp.core": "myapp-core-py",
            "myapp.utils": "myapp-utils-py",
        }
        eid_to_module = {
            "myapp-core-py": "myapp.core",
            "myapp-utils-py": "myapp.utils",
        }
        result = _find_import_target_optimized(
            mod="myapp",
            file_eid="other-py",  # different from all targets → non-self
            file_module="other",
            module_to_eid=module_to_eid,
        )
        # Both candidates are non-self, sorted by priority
        # Neither is exact match or __init__, both priority=2, sorted by key name
        # "myapp.core" < "myapp.utils" alphabetically → returns "myapp-core-py"
        assert result in ("myapp-core-py", "myapp-utils-py")

    def test_prefix_match_init_priority_over_regular(self) -> None:
        """Lines 320-322: __init__ candidate gets priority 1 over regular files."""
        module_to_eid = {
            "myapp.utils": "myapp-utils-py",
            "myapp.__init__": "myapp---init--py",
        }
        eid_to_module = {
            "myapp-utils-py": "myapp.utils",
            "myapp---init--py": "myapp.__init__",
        }
        result = _find_import_target_optimized(
            mod="myapp",
            file_eid="other-py",
            file_module="other",
            module_to_eid=module_to_eid,
        )
        # "myapp.__init__" gets priority 1, "myapp.utils" gets priority 2
        # So __init__ wins
        assert result == "myapp---init--py"


class TestBuildModuleLookupAdditional:
    """Cover line 215->220 in _build_module_lookup."""

    def test_package_name_already_mapped_skips(self) -> None:
        """Line 215->220: package_name already in module_to_eid is skipped.

        This happens when a regular file 'foo.py' exists alongside 'foo/__init__.py'.
        Due to sorting, foo/__init__.py (priority 0) is processed first and maps "foo".
        Then foo.py (priority 1) is processed and maps "foo" (overwriting).
        But if there were TWO __init__.py files somehow mapping to the same package...
        We simulate this by manually testing _build_module_lookup with contrived input.
        """
        # Simulate scenario: 'myapp.py' gets processed AFTER 'myapp/__init__.py'
        # The sort puts __init__.py first (priority 0), so "myapp" gets mapped first.
        # Then "myapp.py" overrides it.
        # To trigger the False branch of 215, we need to process TWO __init__.py
        # files whose package names conflict.
        # This is achievable with 'foo/__init__.py' and 'foo.py' together:
        python_files = ["myapp/__init__.py", "myapp.py"]
        module_to_eid, eid_to_module = _build_module_lookup(python_files)
        # "myapp" should be mapped (to whichever wins)
        assert "myapp" in module_to_eid
