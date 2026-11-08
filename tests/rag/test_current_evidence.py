"""Current RAG evidence is qualified against local files, never cached claims."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from henchman.config.schema import RagSettings, ToolSettings
from henchman.rag.chunker import TextChunker
from henchman.rag.indexer import GitFileIndexer
from henchman.rag.repo_id import compute_repository_id, get_repository_index_dir
from henchman.rag.store import SearchResult, VectorStore
from henchman.tools.builtins.rag_search import RagSearchTool
from henchman.tools.registry import ToolRegistry


def git(root: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
        timeout=10,
    ).stdout.strip()


@pytest.fixture
def repository(tmp_path: Path) -> Path:
    root = tmp_path / "repository"
    root.mkdir()
    git(root, "init")
    git(root, "config", "user.name", "Offline Test")
    git(root, "config", "user.email", "offline@example.invalid")
    (root / "source.py").write_text("def existing_helper():\n    return 42\n", encoding="utf-8")
    git(root, "add", "source.py")
    git(root, "commit", "-m", "fixture")
    return root


def candidate(root: Path, **changes: object) -> SearchResult:
    text = (root / "source.py").read_text(encoding="utf-8")
    values = {
        "content": text,
        "file_path": "source.py",
        "start_line": 1,
        "end_line": 2,
        "score": 0.9,
        "chunk_id": "source.py::0",
        "evidence_version": 1,
        "source_sha256": hashlib.sha256((root / "source.py").read_bytes()).hexdigest(),
        "repository_id": compute_repository_id(root),
        "indexed_revision": git(root, "rev-parse", "HEAD"),
    }
    values.update(changes)
    return SearchResult(**values)


def search_tool(root: Path, *items: SearchResult) -> tuple[RagSearchTool, MagicMock]:
    store = MagicMock()
    store.collection_id = "00000000-0000-0000-0000-000000000001"
    store.search.return_value = list(items)
    return RagSearchTool(store, project_root=root), store


def test_same_remote_clones_have_distinct_cache_authorities(
    repository: Path, tmp_path: Path
) -> None:
    clone = tmp_path / "clone"
    git(tmp_path, "clone", str(repository), str(clone))
    for root in (repository, clone):
        git(root, "remote", "remove", "origin") if root == clone else None
        git(root, "remote", "add", "origin", "https://example.invalid/shared/repo.git")
    assert compute_repository_id(repository) != compute_repository_id(clone)


@pytest.mark.parametrize("changed_during_read", [False, True])
def test_windows_path_creation_time_and_descriptor_change_time_are_distinct(
    repository: Path, monkeypatch, changed_during_read: bool,
) -> None:
    from henchman.rag import evidence

    path_info = (repository / "source.py").stat()
    creation_time = getattr(path_info, "st_birthtime_ns", path_info.st_ctime_ns)

    class WindowsStatOs:
        name = "nt"

        def __init__(self):
            self.observations = 0

        def __getattr__(self, name):
            return getattr(os, name)

        def fstat(self, descriptor):
            info = os.fstat(descriptor)
            self.observations += 1
            fields = {name: getattr(info, name) for name in dir(info) if name.startswith("st_")}
            # CPython Windows path stat keeps creation time in ctime, whereas
            # descriptor fstat can expose last change time (cpython#157671).
            fields["st_birthtime_ns"] = creation_time
            fields["st_ctime_ns"] = creation_time + 100
            if changed_during_read and self.observations > 1:
                fields["st_ctime_ns"] += 100
            return SimpleNamespace(**fields)

    monkeypatch.setattr(evidence, "os", WindowsStatOs())
    workspace = evidence.WorkspaceBinding.bind(repository).snapshot()
    if changed_during_read:
        with pytest.raises(evidence.EvidenceUnavailable, match="source_changed_during_read"):
            evidence.read_source(workspace, "source.py")
    else:
        snapshot = evidence.read_source(workspace, "source.py")
        assert snapshot.sha256 == hashlib.sha256((repository / "source.py").read_bytes()).hexdigest()


def test_cache_identity_is_stable_across_local_commits(repository: Path) -> None:
    before = compute_repository_id(repository)
    (repository / "source.py").write_text("def existing_helper():\n    return 43\n")
    git(repository, "commit", "-am", "second")
    assert compute_repository_id(repository) == before


async def test_bound_search_returns_current_provenance(repository: Path) -> None:
    item = candidate(repository)
    tool, store = search_tool(repository, item)
    result = await tool.execute(query="existing helper")
    assert result.success
    evidence = json.loads(result.content)
    assert evidence["items"][0]["source_sha256"] == item.source_sha256
    assert evidence["items"][0]["current_revision"] == git(repository, "rev-parse", "HEAD")
    assert evidence["items"][0]["content"] == item.content
    assert evidence["items"][0]["freshness"] == "current_file_verified"
    assert evidence["items"][0]["retrieval_reason"] == "semantic_similarity"
    store.search.assert_called_once_with("existing helper", top_k=5)


async def test_unbound_legacy_constructor_refuses_without_store_work() -> None:
    store = MagicMock()
    store.collection_id = "00000000-0000-0000-0000-000000000001"
    result = await RagSearchTool(store).execute(query="helper")
    assert not result.success and "bound" in result.error.lower()
    store.search.assert_not_called()


async def test_legacy_metadata_is_unavailable_not_current(repository: Path) -> None:
    legacy = SearchResult("legacy-private-content", "source.py", 1, 2, 0.9, "source.py::0")
    tool, _ = search_tool(repository, legacy)
    result = await tool.execute(query="helper")
    assert not result.success
    assert "legacy-private-content" not in result.content
    assert "reindex" in result.content.lower()


@pytest.mark.parametrize("change", ["write", "delete", "branch", "untrack"])
async def test_changed_or_deleted_candidates_never_publish_stored_text(
    repository: Path, change: str
) -> None:
    item = candidate(repository)
    tool, _ = search_tool(repository, item)
    if change == "delete":
        (repository / "source.py").unlink()
    elif change == "untrack":
        git(repository, "rm", "--cached", "source.py")
    else:
        if change == "branch":
            git(repository, "checkout", "-b", "other")
        (repository / "source.py").write_text("def replacement():\n    return 99\n")
        if change == "branch":
            git(repository, "commit", "-am", "different source")
    result = await tool.execute(query="helper")
    assert not result.success
    assert "def existing_helper" not in result.content
    assert not json.loads(result.content)["items"]


@pytest.mark.parametrize(
    "path", ["../foreign.py", "/tmp/foreign.py", "C:\\foreign.py", ".git/config"]
)
async def test_foreign_paths_are_rejected_before_content_read(repository: Path, path: str) -> None:
    tool, _ = search_tool(
        repository, candidate(repository, file_path=path, content="foreign-private-content")
    )
    result = await tool.execute(query="helper")
    assert not result.success and "foreign-private-content" not in result.content


async def test_candidate_from_other_workspace_is_not_relabelled(repository: Path) -> None:
    tool, _ = search_tool(repository, candidate(repository, repository_id="f" * 16))
    result = await tool.execute(query="helper")
    assert not result.success and "def existing_helper" not in result.content


@pytest.mark.parametrize("top_k", [0, -1, 21, True, 1.5, "2"])
async def test_query_limits_precede_store_work(repository: Path, top_k: object) -> None:
    tool, store = search_tool(repository)
    result = await tool.execute(query="helper", top_k=top_k)
    assert not result.success
    store.search.assert_not_called()


def test_store_limits_precede_embedding_work() -> None:
    store = object.__new__(VectorStore)
    store.embedder = MagicMock()
    store.collection = MagicMock()
    with pytest.raises(ValueError):
        store.search("query", top_k=21)
    with pytest.raises(ValueError):
        store.search("x" * 2049)
    store.embedder.embed_query.assert_not_called()
    store.collection.query.assert_not_called()


def test_config_rejects_unbounded_top_k() -> None:
    with pytest.raises(ValueError):
        RagSettings(top_k=21)


async def test_publication_rechecks_after_report_serialization(
    repository: Path, monkeypatch
) -> None:
    from henchman.tools.builtins import rag_search

    tool, _ = search_tool(repository, candidate(repository))
    dumps = json.dumps

    def mutate(value, *args, **kwargs):
        if isinstance(value, dict) and value.get("items"):
            (repository / "source.py").write_text("replacement after inspection\n")
        return dumps(value, *args, **kwargs)

    monkeypatch.setattr(rag_search.json, "dumps", mutate)
    result = await tool.execute(query="helper")
    assert not result.success and "def existing_helper" not in result.content


async def test_workspace_revision_change_during_query_refuses_publication(repository: Path) -> None:
    item = candidate(repository)
    tool, store = search_tool(repository, item)

    def change(*_args, **_kwargs):
        git(repository, "commit", "--allow-empty", "-m", "concurrent")
        return [item]

    store.search.side_effect = change
    result = await tool.execute(query="helper")
    assert not result.success and "def existing_helper" not in result.content


async def test_restriction_refuses_before_query_or_enumeration(repository: Path) -> None:
    tool, store = search_tool(repository)
    registry = ToolRegistry()
    registry.register(tool)
    registry.restrict_tool_settings(ToolSettings(filesystem_read_roots=[]), project_root=repository)
    result = await registry.execute("rag_search", {"query": "helper"})
    assert not result.success
    store.search.assert_not_called()


def test_indexer_hashes_the_same_snapshot_it_embeds(repository: Path, tmp_path: Path) -> None:
    store = MagicMock()
    store.collection_id = "00000000-0000-0000-0000-000000000001"
    store.count.return_value = 1
    embedder = SimpleNamespace(
        model_name="offline-fixture", embed=lambda values: [[1.0, 0.0] for _ in values]
    )
    indexer = GitFileIndexer(
        repository, store, embedder, TextChunker(), manifest_path=tmp_path / "manifest.json"
    )
    indexer.index()
    chunk = store.add_chunks.call_args.args[0][0]
    assert (
        chunk.source_sha256 == hashlib.sha256((repository / "source.py").read_bytes()).hexdigest()
    )
    assert chunk.repository_id == compute_repository_id(repository)
    assert chunk.indexed_revision == git(repository, "rev-parse", "HEAD")


def test_index_mutation_during_embedding_cannot_publish_current_metadata(
    repository: Path, tmp_path: Path
) -> None:
    store = MagicMock()
    store.collection_id = "00000000-0000-0000-0000-000000000001"
    store.count.return_value = 0

    def mutate(values):
        (repository / "source.py").write_text("changed during embedding\n")
        return [[1.0, 0.0] for _ in values]

    indexer = GitFileIndexer(
        repository,
        store,
        SimpleNamespace(model_name="offline-fixture", embed=mutate),
        TextChunker(),
        manifest_path=tmp_path / "manifest.json",
    )
    with pytest.raises((ValueError, OSError), match="changed"):
        indexer.index()
    store.add_chunks.assert_not_called()


def test_versioned_cache_does_not_select_shared_legacy_directory(
    repository: Path, tmp_path: Path
) -> None:
    url = "https://example.invalid/shared/repo.git"
    git(repository, "remote", "add", "origin", url)
    cache = tmp_path / "cache"
    legacy = cache / hashlib.sha256(url.lower().removesuffix(".git").encode()).hexdigest()[:16]
    legacy.mkdir(parents=True)
    sentinel = legacy / "manifest.json"
    sentinel.write_text("legacy original")
    assert get_repository_index_dir(repository, cache) != legacy
    assert sentinel.read_text() == "legacy original"


async def test_replaced_repository_metadata_requires_new_binding(repository: Path) -> None:
    import shutil

    tool, store = search_tool(repository, candidate(repository))
    old = repository / ".git"
    replacement = repository / "replacement-git"
    shutil.copytree(old, replacement)
    old.rename(repository / "original-git")
    replacement.rename(old)
    result = await tool.execute(query="helper")
    assert not result.success
    store.search.assert_not_called()


async def test_empty_uninitialized_runtime_index_requires_reindex_without_embedding(
    repository: Path, tmp_path: Path
) -> None:
    store = MagicMock()
    store.collection_id = "00000000-0000-0000-0000-000000000001"
    store.search.return_value = []
    manifest = tmp_path / "not-created" / "manifest.json"
    tool = RagSearchTool(store, project_root=repository, manifest_path=manifest)
    result = await tool.execute(query="helper")
    assert not result.success and "reindex" in result.content
    store.search.assert_not_called()
    assert not manifest.parent.exists()


def test_invalid_manifest_is_not_interpreted_as_empty_index(tmp_path: Path) -> None:
    from henchman.rag.indexer import IndexManifest

    path = tmp_path / "manifest.json"
    path.write_text("{broken")
    with pytest.raises(ValueError, match="manifest"):
        IndexManifest.load(path)
    assert path.read_text() == "{broken"


async def test_real_offline_store_reindex_and_runtime_binding_leave_legacy_untouched(
    repository: Path,
    tmp_path: Path,
    monkeypatch,
) -> None:
    from henchman.rag import embedder as embedder_module
    from henchman.rag.system import initialize_rag

    embedder = SimpleNamespace(
        model_name="offline-fixture",
        embed=lambda values: [[1.0, 0.0] for _ in values],
        embed_query=MagicMock(return_value=[1.0, 0.0]),
    )
    monkeypatch.setattr(embedder_module, "FastEmbedProvider", lambda **_kwargs: embedder)
    old = repository / ".henchman"
    old.mkdir()
    (old / "rag_manifest.json").write_text('{"legacy":"do not replace"}')
    (old / "rag_index").mkdir()
    (old / "rag_index" / "original").write_text("legacy bytes")
    system = initialize_rag(
        RagSettings(cache_dir=str(tmp_path / "cache")), git_root=repository, index=False
    )
    assert system is not None
    unavailable = await system.search_tool.execute(query="helper")
    assert not unavailable.success
    embedder.embed_query.assert_not_called()
    from rich.console import Console

    from henchman.cli.commands import CommandContext
    from henchman.cli.commands.rag import RagCommand

    context = CommandContext(console=Console(), args=["reindex"])
    context.repl = SimpleNamespace(rag_system=system)
    await RagCommand().execute(context)
    current = await system.search_tool.execute(query="helper")
    assert current.success and "existing_helper" in current.content
    (repository / "source.py").write_text("def changed_helper():\n    return 99\n")
    assert not (await system.search_tool.execute(query="helper")).success
    system.index()
    refreshed = await system.search_tool.execute(query="helper")
    assert refreshed.success and "changed_helper" in refreshed.content
    assert "existing_helper" not in refreshed.content
    assert (old / "rag_manifest.json").read_text() == '{"legacy":"do not replace"}'
    assert (old / "rag_index" / "original").read_text() == "legacy bytes"


async def test_output_budget_omits_whole_candidate_with_explicit_diagnostic(
    repository: Path,
) -> None:
    content = "x" * 40_000 + "\nsecond line\n"
    (repository / "source.py").write_text(content)
    tool, _ = search_tool(repository, candidate(repository))
    result = await tool.execute(query="helper")
    assert not result.success
    assert len(result.content.encode()) <= 32 * 1024
    report = json.loads(result.content)
    assert not report["items"]
    assert "output_byte_budget_exceeded" in report["diagnostics"]


async def test_oversized_source_is_not_read_or_published(repository: Path) -> None:
    item = candidate(repository)
    (repository / "source.py").write_bytes(b"a" * (1024 * 1024 + 1))
    tool, _ = search_tool(repository, item)
    result = await tool.execute(query="helper")
    assert not result.success and "source_byte_budget_exceeded" in result.content
    assert "def existing_helper" not in result.content


async def test_real_store_failure_is_not_a_successful_empty_result(repository: Path) -> None:
    tool, store = search_tool(repository)
    store.search.side_effect = RuntimeError("offline index failure")
    result = await tool.execute(query="helper")
    assert not result.success and "offline index failure" in result.error
    assert store.search.call_count == 1


async def test_linked_worktree_has_its_own_current_evidence(
    repository: Path, tmp_path: Path
) -> None:
    linked = tmp_path / "linked"
    git(repository, "worktree", "add", "-b", "linked-branch", str(linked))
    assert compute_repository_id(linked) != compute_repository_id(repository)
    tool, _ = search_tool(linked, candidate(linked))
    result = await tool.execute(query="helper")
    assert result.success
    assert result.structured_content["items"][0]["repository_id"] == compute_repository_id(linked)


async def test_unchanged_file_after_new_commit_discloses_historical_ranking(
    repository: Path,
) -> None:
    indexed = candidate(repository)
    tool, _ = search_tool(repository, indexed)
    git(repository, "commit", "--allow-empty", "-m", "new revision")
    result = await tool.execute(query="helper")
    assert result.success
    report = json.loads(result.content)
    assert report["items"][0]["indexed_revision"] == indexed.indexed_revision
    assert report["items"][0]["current_revision"] != indexed.indexed_revision
    assert "not all current repository files" in " ".join(report["limitations"])


@pytest.mark.parametrize("link_type", ["symlink", "hardlink"])
async def test_replaced_link_never_publishes_external_source(
    repository: Path,
    tmp_path: Path,
    link_type: str,
) -> None:
    import os

    item = candidate(repository)
    tool, _ = search_tool(repository, item)
    external = tmp_path / "external.py"
    external.write_text(item.content)
    path = repository / "source.py"
    path.unlink()
    try:
        if link_type == "symlink":
            path.symlink_to(external)
        else:
            os.link(external, path)
    except OSError as exc:
        pytest.skip(f"Platform cannot create {link_type}: {exc}")
    result = await tool.execute(query="helper")
    assert not result.success
    assert "def existing_helper" not in result.content


async def test_replaced_root_refuses_before_store_query(repository: Path) -> None:
    tool, store = search_tool(repository, candidate(repository))
    old = repository.with_name("original-root")
    repository.rename(old)
    repository.mkdir()
    result = await tool.execute(query="helper")
    assert not result.success and "repository_root_changed" in result.error
    store.search.assert_not_called()


def test_manifest_replace_failure_preserves_original(repository: Path, monkeypatch) -> None:
    from henchman.rag.indexer import IndexManifest

    path = repository / "manifest.json"
    path.write_text('{"files":{}}')
    original = path.read_bytes()
    failure = OSError("owned replacement failure")

    def refuse(*_args):
        raise failure

    monkeypatch.setattr("henchman.rag.indexer.os.replace", refuse)
    with pytest.raises(OSError) as caught:
        IndexManifest(files={"new.py": "digest"}).save(path)
    assert caught.value is failure
    assert path.read_bytes() == original
    assert not list(repository.glob(".manifest.json.*"))


async def test_source_budget_does_not_read_an_extra_candidate(repository: Path) -> None:
    items = []
    content = "a" * (1024 * 1024 - 1) + "\n"
    digest = hashlib.sha256(content.encode()).hexdigest()
    for index in range(6):
        name = f"large-{index}.py"
        (repository / name).write_bytes(content.encode())
        git(repository, "add", name)
        items.append(
            candidate(
                repository,
                file_path=name,
                content=content,
                start_line=1,
                end_line=1,
                source_sha256=digest,
            )
        )
    tool, _ = search_tool(repository, *items)
    result = await tool.execute(query="helper", top_k=6)
    report = json.loads(result.content)
    assert not result.success
    assert "source_byte_budget_exceeded" in report["diagnostics"]
    assert "output_byte_budget_exceeded" in report["diagnostics"]
    assert not report["items"]
    assert len(result.content.encode()) <= 32 * 1024


async def test_publication_revalidates_each_unique_file_once(repository: Path, monkeypatch) -> None:
    from henchman.rag import evidence
    from henchman.tools.builtins import rag_search

    original = evidence.read_source
    observed: list[str] = []

    def observe(workspace, relative, **kwargs):
        observed.append(relative)
        return original(workspace, relative, **kwargs)

    monkeypatch.setattr(evidence, "read_source", observe)
    monkeypatch.setattr(rag_search, "read_source", observe)
    tool, _ = search_tool(repository, *[candidate(repository) for _ in range(20)])
    result = await tool.execute(query="helper", top_k=20)
    assert result.success
    assert observed == ["source.py", "source.py"]


async def test_store_error_output_is_bounded_with_visible_truncation(repository: Path) -> None:
    tool, store = search_tool(repository)
    store.search.side_effect = RuntimeError("failure " + "x" * 100_000)
    result = await tool.execute(query="helper")
    assert not result.success
    assert len(result.content.encode()) <= 32 * 1024
    assert "truncated" in result.error
    assert store.search.call_count == 1


async def test_oversized_error_does_not_publish_a_split_unregistered_credential(
    repository: Path,
) -> None:
    tool, store = search_tool(repository)
    credential = "runtime-credential-with-a-private-tail"
    store.search.side_effect = RuntimeError("x" * 1010 + credential + "z" * 2000)
    result = await tool.execute(query="helper")
    assert not result.success
    assert credential[:14] not in result.content
    assert credential[:14] not in result.error
    assert "truncated" in result.error


def test_standalone_indexer_default_does_not_overwrite_legacy_manifest(repository: Path) -> None:
    old = repository / ".henchman" / "rag_manifest.json"
    old.parent.mkdir()
    original = '{"files": {}, "legacy": "preserve original"}'
    old.write_text(original)
    store = MagicMock()
    store.collection_id = "00000000-0000-0000-0000-000000000001"
    store.count.return_value = 1
    embedder = SimpleNamespace(model_name="offline", embed=lambda values: [[1.0] for _ in values])
    indexer = GitFileIndexer(repository, store, embedder, TextChunker())
    assert indexer.manifest_path != old
    indexer.index()
    assert old.read_text() == original
    assert json.loads(indexer.manifest_path.read_text())["evidence_version"] == 1


@pytest.fixture
def indexed_system(repository: Path, tmp_path: Path, monkeypatch):
    from henchman.rag import embedder as embedder_module
    from henchman.rag.system import initialize_rag

    embedding = SimpleNamespace(
        model_name="offline",
        embed=MagicMock(side_effect=lambda values: [[1.0, 0.0] for _ in values]),
        embed_query=MagicMock(return_value=[1.0, 0.0]),
    )
    monkeypatch.setattr(embedder_module, "FastEmbedProvider", lambda **_kwargs: embedding)
    settings = RagSettings(cache_dir=str(tmp_path / "cache"), embedding_model="offline")
    system = initialize_rag(settings, git_root=repository, index=False)
    assert system is not None
    system.index()
    return system, settings, embedding


@pytest.mark.parametrize("empty", [False, True])
async def test_lost_collection_requires_explicit_reindex_even_for_empty_corpus(
    repository: Path,
    indexed_system,
    empty: bool,
) -> None:
    from henchman.rag.system import initialize_rag

    system, settings, embedding = indexed_system
    if empty:
        (repository / "source.py").write_text(" \n\t\n")
        system.index()
    assert (await system.search_tool.execute(query="helper")).success
    original_manifest = system.manifest_path.read_bytes()
    system.store.client.delete_collection(system.store.collection_name)
    resumed = initialize_rag(settings, git_root=repository, index=False)
    assert resumed is not None
    assert resumed.manifest_path.read_bytes() == original_manifest
    embedding.embed_query.reset_mock()
    unavailable = await resumed.search_tool.execute(query="helper")
    assert not unavailable.success, unavailable.content
    assert "index" in unavailable.error
    embedding.embed_query.assert_not_called()
    resumed.index()
    current = await resumed.search_tool.execute(query="helper")
    assert current.success
    assert bool(current.structured_content["items"]) is not empty


async def test_failed_full_reindex_does_not_requalify_empty_collection(indexed_system) -> None:
    system, _, embedding = indexed_system
    original_manifest = system.manifest_path.read_bytes()
    embedding.embed.side_effect = RuntimeError("offline embedding failure")
    with pytest.raises(RuntimeError, match="offline embedding failure"):
        system.index(force=True)
    assert system.manifest_path.read_bytes() != original_manifest
    assert json.loads(system.manifest_path.read_text())["collection_id"] is None
    embedding.embed_query.reset_mock()
    result = await system.search_tool.execute(query="helper")
    assert not result.success, result.content
    embedding.embed_query.assert_not_called()


async def test_live_deleted_collection_refuses_before_query_embedding(indexed_system) -> None:
    system, _, embedding = indexed_system
    system.store.client.delete_collection(system.store.collection_name)
    result = await system.search_tool.execute(query="helper")
    assert not result.success
    embedding.embed_query.assert_not_called()


async def test_collection_lost_after_query_cannot_publish(indexed_system, monkeypatch) -> None:
    system, _, _ = indexed_system
    original = system.store.search

    def query_then_delete(*args, **kwargs):
        result = original(*args, **kwargs)
        system.store.client.delete_collection(system.store.collection_name)
        return result

    monkeypatch.setattr(system.store, "search", query_then_delete)
    result = await system.search_tool.execute(query="helper")
    assert not result.success
    assert "existing_helper" not in result.content


async def test_git_environment_cannot_redirect_bound_repository(
    repository: Path,
    tmp_path: Path,
    monkeypatch,
) -> None:
    import os

    expected_revision = git(repository, "rev-parse", "HEAD")
    other = tmp_path / "foreign"
    other.mkdir()
    git(other, "init")
    git(other, "config", "user.name", "Offline Test")
    git(other, "config", "user.email", "offline@example.invalid")
    (other / "source.py").write_text("foreign revision\n")
    (other / "foreign.py").write_text("foreign only\n")
    git(other, "add", ".")
    git(other, "commit", "-m", "other")
    assert git(other, "rev-parse", "HEAD") != expected_revision
    tool, _ = search_tool(repository, candidate(repository))
    indexer = GitFileIndexer(repository, MagicMock(), MagicMock(), TextChunker())
    monkeypatch.setenv("GIT_DIR", str(other / ".git"))
    monkeypatch.setenv("GIT_WORK_TREE", str(other))
    result = await tool.execute(query="helper")
    assert result.success
    assert result.structured_content["current_revision"] == expected_revision
    assert indexer.get_tracked_files() == [repository / "source.py"]
    assert os.environ["GIT_DIR"] == str(other / ".git")
    assert os.environ["GIT_WORK_TREE"] == str(other)


async def test_git_index_override_does_not_restore_untracked_authority(
    repository: Path,
    tmp_path: Path,
    monkeypatch,
) -> None:
    import os
    import shutil

    tool, _ = search_tool(repository, candidate(repository))
    indexer = GitFileIndexer(repository, MagicMock(), MagicMock(), TextChunker())
    saved = tmp_path / "saved-index"
    shutil.copyfile(repository / ".git" / "index", saved)
    git(repository, "rm", "--cached", "source.py")
    monkeypatch.setenv("GIT_INDEX_FILE", str(saved))
    result = await tool.execute(query="helper")
    assert not result.success
    assert "source_not_tracked" in result.content
    assert "existing_helper" not in result.content
    assert indexer.get_tracked_files() == []
    assert os.environ["GIT_INDEX_FILE"] == str(saved)


async def test_failed_incremental_insert_invalidates_readiness(
    indexed_system, repository: Path, monkeypatch
) -> None:
    system, _, embedding = indexed_system
    original_add = system.store.add_chunks
    (repository / "source.py").write_text("def existing_helper():\n    return 43\n")
    failure = RuntimeError("offline insertion failure")

    def refuse(*_args):
        raise failure

    monkeypatch.setattr(system.store, "add_chunks", refuse)
    with pytest.raises(RuntimeError) as caught:
        system.index()
    assert caught.value is failure
    assert system.store.count() == 0
    result = await system.search_tool.execute(query="helper")
    assert not result.success
    embedding.embed_query.assert_not_called()
    assert json.loads(system.manifest_path.read_text())["collection_id"] is None
    monkeypatch.setattr(system.store, "add_chunks", original_add)
    system.index()
    recovered = await system.search_tool.execute(query="helper")
    assert recovered.success and "return 43" in recovered.content


def test_pending_manifest_write_failure_prevents_store_mutation(
    indexed_system, monkeypatch
) -> None:
    from henchman.rag.indexer import IndexManifest

    system, _, _ = indexed_system
    original_manifest = system.manifest_path.read_bytes()
    failure = OSError("pending manifest write failure")
    clear = MagicMock(wraps=system.store.clear)
    monkeypatch.setattr(system.store, "clear", clear)

    def refuse(*_args):
        raise failure

    monkeypatch.setattr(IndexManifest, "save", refuse)
    with pytest.raises(OSError) as caught:
        system.index(force=True)
    assert caught.value is failure
    clear.assert_not_called()
    assert system.store.count() == 1
    assert system.manifest_path.read_bytes() == original_manifest


@pytest.mark.parametrize("finish_index", [False, True])
async def test_query_cannot_publish_across_index_readiness_cycle(
    indexed_system,
    repository: Path,
    monkeypatch,
    finish_index: bool,
) -> None:
    system, _, _ = indexed_system
    original_search = system.store.search
    original_add = system.store.add_chunks
    original_single = system.indexer._index_single_file
    original_source = (repository / "source.py").read_bytes()
    initial = json.loads(system.manifest_path.read_text())
    observations = {}

    def restore_before_index(abs_path, relative):
        (repository / "source.py").write_bytes(original_source)
        return original_single(abs_path, relative)

    def insert(*args, **kwargs):
        observations["pending"] = json.loads(system.manifest_path.read_text())
        observations["empty"] = original_search("helper", 5)
        if not finish_index:
            raise RuntimeError("owned interrupted insertion")
        return original_add(*args, **kwargs)

    def query_during_index(*_args, **_kwargs):
        (repository / "source.py").write_text("def existing_helper():\n    return 43\n")
        if finish_index:
            system.index()
        else:
            with pytest.raises(RuntimeError, match="owned interrupted insertion"):
                system.index()
        return observations["empty"]

    monkeypatch.setattr(system.indexer, "_index_single_file", restore_before_index)
    monkeypatch.setattr(system.store, "add_chunks", insert)
    monkeypatch.setattr(system.store, "search", query_during_index)
    result = await system.search_tool.execute(query="helper")
    assert not result.success, result.content
    assert observations["pending"]["collection_id"] is None
    assert observations["empty"] == []
    final = json.loads(system.manifest_path.read_text())
    assert final["generation_id"] != initial["generation_id"]
    if finish_index:
        assert final["files"] == initial["files"]
        assert final["collection_id"] == initial["collection_id"]
        assert system.store.count() == 1


@pytest.mark.parametrize("field", ["collection_id", "generation_id"])
async def test_malformed_manifest_generation_diagnostic_omits_value(
    indexed_system, field: str
) -> None:
    system, _, embedding = indexed_system
    manifest = json.loads(system.manifest_path.read_text())
    private = "private-canary-" + "z" * 19
    manifest[field] = private
    system.manifest_path.write_text(json.dumps(manifest))
    result = await system.search_tool.execute(query="helper")
    assert not result.success
    assert "privatecanary" not in result.content.replace("-", "")
    assert "privatecanary" not in result.error.replace("-", "")
    embedding.embed_query.assert_not_called()


@pytest.mark.parametrize("empty", [False, True])
async def test_changed_query_embedding_model_requires_explicit_reindex(
    repository: Path,
    indexed_system,
    empty: bool,
) -> None:
    from henchman.rag.system import initialize_rag

    system, settings, embedding = indexed_system
    if empty:
        (repository / "source.py").write_text(" \n\t\n")
        system.index()
    settings.embedding_model = "changed-offline-model"
    embedding.model_name = settings.embedding_model
    resumed = initialize_rag(settings, git_root=repository, index=False)
    assert resumed is not None
    unavailable = await resumed.search_tool.execute(query="helper")
    assert not unavailable.success, unavailable.content
    embedding.embed_query.assert_not_called()
    resumed.index()
    current = await resumed.search_tool.execute(query="helper")
    assert current.success
    assert bool(current.structured_content["items"]) is not empty
    assert json.loads(resumed.manifest_path.read_text())["model_name"] == embedding.model_name


@pytest.mark.parametrize("model_name", [None, "", 42])
async def test_invalid_manifest_embedding_profile_refuses_before_query(
    indexed_system, model_name
) -> None:
    system, _, embedding = indexed_system
    manifest = json.loads(system.manifest_path.read_text())
    if model_name is None:
        manifest.pop("model_name")
    else:
        manifest["model_name"] = model_name
    system.manifest_path.write_text(json.dumps(manifest))
    result = await system.search_tool.execute(query="helper")
    assert not result.success
    embedding.embed_query.assert_not_called()


async def test_query_embedding_profile_cannot_change_before_publication(
    indexed_system, monkeypatch
) -> None:
    system, _, embedding = indexed_system
    original = system.store.search

    def search_then_replace(*args, **kwargs):
        result = original(*args, **kwargs)
        embedding.model_name = "replacement-model"
        return result

    monkeypatch.setattr(system.store, "search", search_then_replace)
    result = await system.search_tool.execute(query="helper")
    assert not result.success
    assert "existing_helper" not in result.content


def test_index_profile_change_during_embedding_cannot_publish_ready_manifest(
    indexed_system, repository: Path,
) -> None:
    system, _, embedding = indexed_system
    (repository / "source.py").write_text("def existing_helper():\n    return 43\n")

    def change_model(values):
        embedding.model_name = "replacement-profile"
        return [[1.0, 0.0] for _ in values]

    embedding.embed.side_effect = change_model
    with pytest.raises(ValueError, match="profile"):
        system.index()
    assert json.loads(system.manifest_path.read_text())["collection_id"] is None
