"""Execute release workflow scripts against offline GitHub API fixtures."""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
from pathlib import Path
from typing import Any

import pytest
import yaml

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
NODE = shutil.which("node")

NODE_HARNESS = r"""
const nativeRequire = require;
const input = JSON.parse(require('fs').readFileSync(0, 'utf8'));
const calls = [];
const outputs = {};
const defaults = {
  listPullRequestsAssociatedWithCommit: [], listReleases: [], listReleaseAssets: [],
  createRelease: {id: 17, draft: true}, createRef: {}, uploadReleaseAsset: {}, updateRelease: {},
};
const methods = [
  'listPullRequestsAssociatedWithCommit', 'listReleases', 'listReleaseAssets',
  'createRelease', 'createRef', 'getRef', 'uploadReleaseAsset', 'updateRelease',
];
const api = {};
for (const name of methods) {
  api[name] = async (parameters) => {
    calls.push({name, parameters});
    const failure = input.failures?.[name];
    if (failure) throw Object.assign(new Error('fixture ' + name + ' failure'), {status: failure});
    if (name === 'getRef' && !Object.hasOwn(input.responses || {}, name)) {
      throw Object.assign(new Error('fixture missing ref'), {status: 404});
    }
    return {data: Object.hasOwn(input.responses || {}, name)
      ? input.responses[name] : defaults[name]};
  };
}
const github = {
  rest: {repos: api, git: api},
  paginate: async (method, parameters) => (await method(parameters)).data,
};
const core = {setOutput: (name, value) => {outputs[name] = value;}};
const fakeFs = {
  readdirSync: () => ['.gitignore', 'henchman_ai-0.4.1-py3-none-any.whl', 'henchman_ai-0.4.1.tar.gz'],
  readFileSync: (name) => Buffer.from('fixture bytes for ' + name),
};
process.env.RELEASE_TAG = 'v0.4.1';
process.env.RELEASE_PR = '8';
const AsyncFunction = Object.getPrototypeOf(async function(){}).constructor;
(async () => {
  try {
    if (input.expression) {
      const value = new Function('github', 'return (' + input.expression + ')')(input.event);
      process.stdout.write(JSON.stringify({value}));
    } else {
      await new AsyncFunction('github', 'context', 'core', 'require', input.script)(
        github, input.context, core, (name) => {
          if (name === 'crypto') return nativeRequire(name);
          if (name !== 'fs') throw new Error('Unexpected module ' + name);
          return fakeFs;
        });
      process.stdout.write(JSON.stringify({calls, outputs}));
    }
  } catch (error) {
    process.stdout.write(JSON.stringify({calls, outputs, error: error.message}));
  }
})();
"""


def _workflow(filename: str = "release.yml") -> dict[str, Any]:
    return yaml.safe_load(
        (REPOSITORY_ROOT / ".github/workflows" / filename).read_text(encoding="utf-8")
    )


def _steps() -> list[dict[str, Any]]:
    return _workflow()["jobs"]["release"]["steps"]


def _script(*, step_id: str | None = None, name: str | None = None) -> str:
    return next(
        step["with"]["script"]
        for step in _steps()
        if (step_id is not None and step.get("id") == step_id)
        or (name is not None and step.get("name") == name)
    )


def _node(**payload: Any) -> dict[str, Any]:
    if NODE is None:
        pytest.skip("Node is required to execute GitHub Actions inline JavaScript")
    result = subprocess.run(
        [NODE, "-e", NODE_HARNESS],
        input=json.dumps(payload),
        text=True,
        capture_output=True,
        timeout=10,
        check=True,
    )
    return json.loads(result.stdout)


def _context() -> dict[str, Any]:
    return {
        "repo": {"owner": "owner", "repo": "henchman-ai"},
        "payload": {"workflow_run": {"head_sha": "tested-merge-sha"}},
    }


def _merged_pr(**changes: Any) -> dict[str, Any]:
    return {
        "number": 8,
        "merged_at": "2026-10-15T12:00:00Z",
        "base": {"ref": "main"},
        "merge_commit_sha": "tested-merge-sha",
        "milestone": {"title": "v0.4.1"},
        **changes,
    }


def test_resolves_the_merged_main_pr_milestone() -> None:
    result = _node(
        script=_script(step_id="milestone"),
        context=_context(),
        responses={"listPullRequestsAssociatedWithCommit": [_merged_pr()]},
    )
    assert "error" not in result
    assert result["outputs"] == {"title": "v0.4.1", "pr": 8}
    assert result["calls"][0]["parameters"]["commit_sha"] == "tested-merge-sha"


@pytest.mark.parametrize(
    "prs",
    [
        [],
        [_merged_pr(milestone=None)],
        [_merged_pr(), _merged_pr(number=10)],
        [_merged_pr(merged_at=None)],
        [_merged_pr(base={"ref": "development"})],
        [_merged_pr(merge_commit_sha="other-sha")],
    ],
    ids=["absent", "missing-milestone", "ambiguous", "unmerged", "wrong-base", "wrong-sha"],
)
def test_missing_or_ambiguous_release_pr_stops_before_outputs(prs: list[dict[str, Any]]) -> None:
    result = _node(
        script=_script(step_id="milestone"),
        context=_context(),
        responses={"listPullRequestsAssociatedWithCommit": prs},
    )
    assert "release requires" in result["error"]
    assert result["outputs"] == {}


def _event() -> dict[str, Any]:
    return {
        "repository": "owner/henchman-ai",
        "repository_owner": "owner",
        "event": {
            "workflow_run": {
                "conclusion": "success",
                "event": "push",
                "head_branch": "main",
                "head_repository": {"full_name": "owner/henchman-ai"},
                "actor": {"login": "owner"},
            }
        },
    }


def test_successful_main_push_is_the_only_release_trigger() -> None:
    workflow = _workflow()
    trigger = workflow.get("on", workflow.get(True))["workflow_run"]
    assert trigger == {"workflows": ["CI"], "types": ["completed"], "branches": ["main"]}
    assert _node(expression=workflow["jobs"]["release"]["if"], event=_event())["value"]


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("conclusion", "failure"),
        ("event", "pull_request"),
        ("head_branch", "feature"),
        ("head_repository", {"full_name": "fork/henchman-ai"}),
        ("actor", {"login": "contributor"}),
    ],
)
def test_failed_pr_fork_and_untrusted_events_cannot_publish(field: str, value: Any) -> None:
    event = _event()
    event["event"]["workflow_run"][field] = value
    assert not _node(expression=_workflow()["jobs"]["release"]["if"], event=event)["value"]


@pytest.mark.parametrize("preflight", [True, False], ids=["preflight", "finalization"])
def test_conflicting_tag_stops_release(preflight: bool) -> None:
    result = _node(
        script=(
            _script(step_id="existing")
            if preflight
            else _script(name="Tag and publish the GitHub release")
        ),
        context=_context(),
        responses={"getRef": {"object": {"sha": "different-commit"}}},
    )
    assert "another commit" in result["error"]
    assert [call["name"] for call in result["calls"]] == ["getRef"]


def test_tag_permission_errors_are_not_treated_as_missing_tags() -> None:
    result = _node(
        script=_script(name="Tag and publish the GitHub release"),
        context=_context(),
        failures={"getRef": 403},
    )
    assert "getRef failure" in result["error"]
    assert [call["name"] for call in result["calls"]] == ["getRef"]


def test_draft_retry_recovers_existing_release_and_uploads_only_missing_assets() -> None:
    wheel = "henchman_ai-0.4.1-py3-none-any.whl"
    digest = hashlib.sha256(f"fixture bytes for dist/{wheel}".encode()).hexdigest()
    result = _node(
        script=_script(name="Tag and publish the GitHub release"),
        context=_context(),
        responses={
            "getRef": {"object": {"sha": "tested-merge-sha"}},
            "listReleases": [{"id": 31, "tag_name": "v0.4.1", "draft": True}],
            "listReleaseAssets": [{"name": wheel, "digest": f"sha256:{digest}"}],
        },
    )
    assert "error" not in result
    names = [call["name"] for call in result["calls"]]
    assert "createRef" not in names
    assert "createRelease" not in names
    uploads = [
        call["parameters"] for call in result["calls"] if call["name"] == "uploadReleaseAsset"
    ]
    assert len(uploads) == 1
    assert uploads[0]["name"] == "henchman_ai-0.4.1.tar.gz"
    publication = result["calls"][-1]
    assert publication["name"] == "updateRelease"
    assert publication["parameters"]["release_id"] == 31
    assert publication["parameters"]["draft"] is False
    assert publication["parameters"]["target_commitish"] == "tested-merge-sha"


@pytest.mark.parametrize("digest", [None, "sha256:different-contents"])
def test_existing_asset_without_matching_digest_blocks_release(digest: str | None) -> None:
    result = _node(
        script=_script(name="Tag and publish the GitHub release"),
        context=_context(),
        responses={
            "getRef": {"object": {"sha": "tested-merge-sha"}},
            "listReleases": [{"id": 31, "tag_name": "v0.4.1", "draft": True}],
            "listReleaseAssets": [{"name": "henchman_ai-0.4.1-py3-none-any.whl", "digest": digest}],
        },
    )
    assert "asset" in result.get("error", "").lower()
    assert "updateRelease" not in [call["name"] for call in result["calls"]]


def test_tag_targets_tested_commit_and_release_publishes_after_asset_uploads() -> None:
    result = _node(script=_script(name="Tag and publish the GitHub release"), context=_context())
    assert "error" not in result
    calls = result["calls"]
    tag = next(call for call in calls if call["name"] == "createRef")
    assert tag["parameters"]["ref"] == "refs/tags/v0.4.1"
    assert tag["parameters"]["sha"] == "tested-merge-sha"
    draft = next(call for call in calls if call["name"] == "createRelease")
    assert draft["parameters"]["draft"] is True
    assert draft["parameters"]["target_commitish"] == "tested-merge-sha"
    assert "PR #8" in draft["parameters"]["body"]
    assert [call["name"] for call in calls][-3:] == [
        "uploadReleaseAsset",
        "uploadReleaseAsset",
        "updateRelease",
    ]


def test_asset_upload_failure_leaves_release_unpublished() -> None:
    result = _node(
        script=_script(name="Tag and publish the GitHub release"),
        context=_context(),
        failures={"uploadReleaseAsset": 502},
    )
    assert "uploadReleaseAsset failure" in result["error"]
    assert "updateRelease" not in [call["name"] for call in result["calls"]]


def test_distribution_gitignore_is_not_uploaded_as_a_release_asset() -> None:
    result = _node(script=_script(name="Tag and publish the GitHub release"), context=_context())
    assert "error" not in result
    uploaded = {
        call["parameters"]["name"]
        for call in result["calls"]
        if call["name"] == "uploadReleaseAsset"
    }
    assert uploaded == {"henchman_ai-0.4.1-py3-none-any.whl", "henchman_ai-0.4.1.tar.gz"}


def test_publisher_failure_prevents_tagging_and_credentials_stay_in_publish_step() -> None:
    steps = _steps()
    publisher = next(i for i, step in enumerate(steps) if step.get("env", {}).get("PYPI"))
    tagging = next(
        i for i, step in enumerate(steps) if step["name"] == "Tag and publish the GitHub release"
    )
    assert publisher < tagging
    assert "continue-on-error" not in steps[publisher]
    assert "if" not in steps[tagging] or steps[tagging]["if"] == "success()"
    assert steps[publisher]["env"]["PYPI"] == "${{ secrets.PYPI }}"
    assert all("PYPI" not in step.get("env", {}) for i, step in enumerate(steps) if i != publisher)
    assert _workflow()["concurrency"] == {"group": "pypi-release", "cancel-in-progress": False}


def test_retry_artifacts_preserve_each_attempt_and_tested_commit() -> None:
    artifact = next(
        step for step in _steps() if step.get("uses", "").startswith("actions/upload-artifact@")
    )
    name = artifact["with"]["name"]
    assert "${{ github.run_attempt }}" in name
    assert "${{ github.event.workflow_run.head_sha }}" in name
    assert artifact["with"]["path"] == "dist/"
    checkout = next(
        step for step in _steps() if step.get("uses", "").startswith("actions/checkout@")
    )
    assert checkout["with"]["ref"] == "${{ github.event.workflow_run.head_sha }}"


def test_built_provenance_uses_tested_sha_and_is_cleaned_after_failures() -> None:
    job = _workflow()["jobs"]["release"]
    assert job["env"]["RELEASE_SHA"] == "${{ github.event.workflow_run.head_sha }}"
    build = next(step for step in job["steps"] if "uv build" in step.get("run", ""))
    assert build["env"]["RELEASE_PR"] == "${{ steps.milestone.outputs.pr }}"
    assert build["env"]["RELEASE_MILESTONE"] == "${{ steps.milestone.outputs.title }}"
    assert build["run"].index("release.py prepare") < build["run"].index("uv build")
    cleanup = next(
        step for step in job["steps"] if "rm -f src/henchman/_release.json" in step.get("run", "")
    )
    assert cleanup["if"] == "always()"


def test_pr_validation_retains_both_distributions_without_publication_credentials() -> None:
    ci = _workflow("ci.yml")
    assert "main" in ci.get("on", ci.get(True))["pull_request"]["branches"]
    job = ci["jobs"]["build-check"]
    upload = next(
        step for step in job["steps"] if step.get("uses", "").startswith("actions/upload-artifact@")
    )
    assert upload["with"]["path"] == "dist/"
    assert upload["with"]["if-no-files-found"] == "error"
    assert "${{ github.run_attempt }}" in upload["with"]["name"]
    assert "${{ github.sha }}" in upload["with"]["name"]
    assert "secrets.PYPI" not in json.dumps(ci)
