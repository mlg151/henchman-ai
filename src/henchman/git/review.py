"""Pull-request diff analysis, comment drafting, and autofix helpers."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from henchman.config.paths import resolve_project_settings_path
from henchman.git.clients import GitClient, GitHubCliClient, PullRequestComment

Severity = Literal["low", "medium", "high"]
ReviewMode = Literal["general", "security"]


@dataclass(frozen=True, slots=True)
class ReviewFinding:
    """One review finding derived from a diff."""

    code: str
    severity: Severity
    file_path: str
    line_number: int | None
    message: str
    suggestion: str | None
    excerpt: str | None = None
    fixable: bool = False

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-serializable representation."""

        return {
            "code": self.code,
            "severity": self.severity,
            "file_path": self.file_path,
            "line_number": self.line_number,
            "message": self.message,
            "suggestion": self.suggestion,
            "excerpt": self.excerpt,
            "fixable": self.fixable,
        }


@dataclass(frozen=True, slots=True)
class ReviewReport:
    """Structured report from a general or security review."""

    mode: ReviewMode
    target: str
    summary: str
    findings: tuple[ReviewFinding, ...]

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-serializable representation."""

        return {
            "mode": self.mode,
            "target": self.target,
            "summary": self.summary,
            "findings": [finding.to_dict() for finding in self.findings],
        }


@dataclass(frozen=True, slots=True)
class CommentDraft:
    """A drafted reply for one pull-request review comment."""

    comment_id: int
    original_body: str
    draft_reply: str
    path: str | None

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-serializable representation."""

        return {
            "comment_id": self.comment_id,
            "original_body": self.original_body,
            "draft_reply": self.draft_reply,
            "path": self.path,
        }


@dataclass(frozen=True, slots=True)
class CommentReplyResult:
    """Result from sending a review-comment reply."""

    pr_number: int
    comment_id: int
    body: str
    reply_url: str

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-serializable representation."""

        return {
            "pr_number": self.pr_number,
            "comment_id": self.comment_id,
            "body": self.body,
            "reply_url": self.reply_url,
        }


@dataclass(frozen=True, slots=True)
class AutofixChange:
    """Outcome of applying or skipping one fix."""

    finding_code: str
    file_path: str
    line_number: int | None
    applied: bool
    description: str

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-serializable representation."""

        return {
            "finding_code": self.finding_code,
            "file_path": self.file_path,
            "line_number": self.line_number,
            "applied": self.applied,
            "description": self.description,
        }


@dataclass(frozen=True, slots=True)
class AutofixReport:
    """Summary of autofix work."""

    applied_count: int
    skipped_count: int
    changes: tuple[AutofixChange, ...]

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-serializable representation."""

        return {
            "applied_count": self.applied_count,
            "skipped_count": self.skipped_count,
            "changes": [change.to_dict() for change in self.changes],
        }


@dataclass(frozen=True, slots=True)
class _AddedLine:
    """One added line in a unified diff."""

    number: int
    content: str


@dataclass(slots=True)
class _DiffFile:
    """Aggregated added lines for one changed file."""

    path: str
    added_lines: list[_AddedLine]
    removed_count: int = 0


class PullRequestDiffCache:
    """Project-local cache for fetched pull-request diffs."""

    def __init__(self, project_root: Path | None = None) -> None:
        """Initialize the cache."""

        self._project_root = (project_root or Path.cwd()).resolve()
        self._cache_dir = resolve_project_settings_path(self._project_root) / "cache" / "pr_diffs"

    def exists(self, *, pr_number: int, repo_slug: str) -> bool:
        """Return whether a cached diff exists."""

        return self._cache_path(pr_number=pr_number, repo_slug=repo_slug).exists()

    def load(self, *, pr_number: int, repo_slug: str) -> str | None:
        """Load a cached diff when available."""

        cache_path = self._cache_path(pr_number=pr_number, repo_slug=repo_slug)
        if not cache_path.exists():
            return None
        return cache_path.read_text(encoding="utf-8")

    def store(self, *, pr_number: int, repo_slug: str, diff_text: str) -> Path:
        """Persist one diff payload."""

        cache_path = self._cache_path(pr_number=pr_number, repo_slug=repo_slug)
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        cache_path.write_text(diff_text, encoding="utf-8")
        return cache_path

    def invalidate(self, *, pr_number: int, repo_slug: str) -> bool:
        """Remove a cached diff when present."""

        cache_path = self._cache_path(pr_number=pr_number, repo_slug=repo_slug)
        if not cache_path.exists():
            return False
        cache_path.unlink()
        return True

    def get_or_fetch(
        self,
        *,
        pr_number: int,
        repo_slug: str,
        fetcher: Callable[[], str],
        refresh: bool = False,
    ) -> str:
        """Return a cached diff or fetch and store a fresh copy."""

        if not refresh:
            cached = self.load(pr_number=pr_number, repo_slug=repo_slug)
            if cached is not None:
                return cached
        diff_text = fetcher()
        self.store(pr_number=pr_number, repo_slug=repo_slug, diff_text=diff_text)
        return diff_text

    def _cache_path(self, *, pr_number: int, repo_slug: str) -> Path:
        """Return the path used for one cached diff."""

        safe_repo = repo_slug.replace("/", "__")
        return self._cache_dir / f"{safe_repo}__pr_{pr_number}.diff"


class PullRequestReviewer:
    """Review local or pull-request diffs using deterministic heuristics."""

    def __init__(
        self,
        project_root: Path | None = None,
        *,
        git_client: GitClient | None = None,
        github_client: GitHubCliClient | None = None,
        diff_cache: PullRequestDiffCache | None = None,
    ) -> None:
        """Initialize the reviewer."""

        self._project_root = (project_root or Path.cwd()).resolve()
        self._git_client = git_client or GitClient(project_root=self._project_root)
        self._github_client = github_client or GitHubCliClient(project_root=self._project_root)
        self._diff_cache = diff_cache or PullRequestDiffCache(project_root=self._project_root)

    def review(
        self,
        *,
        pr_number: int | None = None,
        mode: ReviewMode = "general",
        refresh: bool = False,
    ) -> ReviewReport:
        """Review the requested diff target."""

        diff_text, target = self._load_diff(pr_number=pr_number, refresh=refresh)
        if not diff_text.strip():
            return ReviewReport(mode=mode, target=target, summary="No changes found.", findings=())
        diff_files = _parse_diff(diff_text)
        if mode == "security":
            findings = _security_findings(diff_files)
        else:
            findings = _general_findings(diff_files)
        summary = "No findings." if not findings else _format_findings_summary(len(findings))
        return ReviewReport(mode=mode, target=target, summary=summary, findings=tuple(findings))

    def _load_diff(self, *, pr_number: int | None, refresh: bool) -> tuple[str, str]:
        """Load a local or cached PR diff plus its target label."""

        if pr_number is not None:
            repo_slug = self._github_client.repo_name_with_owner()
            diff_text = self._diff_cache.get_or_fetch(
                pr_number=pr_number,
                repo_slug=repo_slug,
                refresh=refresh,
                fetcher=lambda: self._github_client.pull_request_diff(
                    pr_number,
                    repo_slug=repo_slug,
                ),
            )
            return diff_text, f"pr#{pr_number}"

        staged_diff = self._git_client.diff(staged=True)
        if staged_diff.strip():
            return staged_diff, "staged"
        return self._git_client.diff(staged=False), "working-tree"


class CommentManager:
    """Draft and send pull-request review-comment replies."""

    def __init__(
        self,
        project_root: Path | None = None,
        *,
        github_client: GitHubCliClient | None = None,
    ) -> None:
        """Initialize the manager."""

        self._github_client = github_client or GitHubCliClient(project_root=project_root)

    def generate(self, *, pr_number: int) -> tuple[CommentDraft, ...]:
        """Generate draft replies for review comments."""

        comments = self._github_client.fetch_review_comments(pr_number)
        return tuple(_build_comment_draft(comment) for comment in comments)

    def respond(self, *, pr_number: int, comment_id: int, body: str) -> CommentReplyResult:
        """Post a reply to one review comment."""

        reply_url = self._github_client.reply_to_review_comment(
            pr_number=pr_number,
            comment_id=comment_id,
            body=body,
        )
        return CommentReplyResult(
            pr_number=pr_number,
            comment_id=comment_id,
            body=body,
            reply_url=reply_url,
        )


class AutofixService:
    """Apply safe, line-oriented fixes for supported review findings."""

    def __init__(
        self,
        project_root: Path | None = None,
        *,
        reviewer: PullRequestReviewer | None = None,
    ) -> None:
        """Initialize the service."""

        self._project_root = (project_root or Path.cwd()).resolve()
        self._reviewer = reviewer or PullRequestReviewer(project_root=self._project_root)

    def autofix(
        self,
        *,
        pr_number: int | None = None,
        refresh: bool = False,
        apply: bool = False,
    ) -> AutofixReport:
        """Collect review findings and optionally apply supported fixes."""

        general_report = self._reviewer.review(pr_number=pr_number, mode="general", refresh=refresh)
        security_report = self._reviewer.review(pr_number=pr_number, mode="security", refresh=refresh)
        findings = (*general_report.findings, *security_report.findings)
        return self.apply_findings(findings, apply=apply)

    def apply_findings(
        self,
        findings: list[ReviewFinding] | tuple[ReviewFinding, ...],
        *,
        apply: bool,
    ) -> AutofixReport:
        """Apply supported fixes for the provided findings."""

        changes: list[AutofixChange] = []
        applied_count = 0
        skipped_count = 0
        grouped_findings = _group_findings_by_file(findings)

        for file_path, file_findings in grouped_findings.items():
            resolved_path = self._resolve_file_path(file_path)
            if not resolved_path.exists():
                for finding in file_findings:
                    skipped_count += 1
                    changes.append(
                        AutofixChange(
                            finding_code=finding.code,
                            file_path=file_path,
                            line_number=finding.line_number,
                            applied=False,
                            description="Skipped because the file does not exist locally.",
                        ),
                    )
                continue

            original_text = resolved_path.read_text(encoding="utf-8")
            ends_with_newline = original_text.endswith("\n")
            lines = original_text.splitlines()

            for finding in sorted(file_findings, key=_sort_key_for_finding, reverse=True):
                applied, description = _apply_line_fix(lines, finding, apply=apply)
                if applied:
                    applied_count += 1
                else:
                    skipped_count += 1
                changes.append(
                    AutofixChange(
                        finding_code=finding.code,
                        file_path=file_path,
                        line_number=finding.line_number,
                        applied=applied,
                        description=description,
                    ),
                )

            if apply:
                updated_text = "\n".join(lines)
                if ends_with_newline:
                    updated_text += "\n"
                resolved_path.write_text(updated_text, encoding="utf-8")

        return AutofixReport(
            applied_count=applied_count,
            skipped_count=skipped_count,
            changes=tuple(changes),
        )

    def _resolve_file_path(self, file_path: str) -> Path:
        """Resolve a finding path against the project root when needed."""

        path = Path(file_path)
        if path.is_absolute():
            return path
        return (self._project_root / path).resolve()


def _parse_diff(diff_text: str) -> tuple[_DiffFile, ...]:
    """Parse added lines from a unified diff."""

    files: list[_DiffFile] = []
    current_file: _DiffFile | None = None
    new_line_number = 0

    for raw_line in diff_text.splitlines():
        if raw_line.startswith("+++ b/"):
            current_file = _DiffFile(path=raw_line.removeprefix("+++ b/"), added_lines=[])
            files.append(current_file)
            continue
        if raw_line.startswith("@@ "):
            new_line_number = _parse_hunk_new_line(raw_line)
            continue
        if current_file is None:
            continue
        if raw_line.startswith("+") and not raw_line.startswith("+++"):
            current_file.added_lines.append(_AddedLine(number=new_line_number, content=raw_line[1:]))
            new_line_number += 1
            continue
        if raw_line.startswith("-") and not raw_line.startswith("---"):
            current_file.removed_count += 1
            continue
        if not raw_line.startswith("\\"):
            new_line_number += 1

    return tuple(files)


def _parse_hunk_new_line(header: str) -> int:
    """Parse the new-file line number from one hunk header."""

    _, _, remainder = header.partition("+")
    number_text, _, _ = remainder.partition(",")
    value, _, _ = number_text.partition(" ")
    return int(value)


def _general_findings(diff_files: tuple[_DiffFile, ...]) -> list[ReviewFinding]:
    """Return general review findings for the diff."""

    findings: list[ReviewFinding] = []
    changed_paths = {diff_file.path for diff_file in diff_files}

    for diff_file in diff_files:
        for line in diff_file.added_lines:
            content = line.content.strip()
            if any(pattern in content for pattern in ('print("', "print('", "breakpoint()", "pdb.set_trace(")):
                findings.append(
                    ReviewFinding(
                        code="debug-statement",
                        severity="medium",
                        file_path=diff_file.path,
                        line_number=line.number,
                        message="Remove debug output before merging.",
                        suggestion="Delete the debug statement or replace it with structured logging.",
                        excerpt=line.content,
                        fixable=True,
                    ),
                )
            if any(token in content for token in ("TODO", "FIXME", "XXX")):
                findings.append(
                    ReviewFinding(
                        code="todo-comment",
                        severity="low",
                        file_path=diff_file.path,
                        line_number=line.number,
                        message="Resolve TODO comments or turn them into tracked work items.",
                        suggestion="Finish the work or remove the temporary comment before merging.",
                        excerpt=line.content,
                    ),
                )
            if content.startswith("except Exception") or content == "except:":
                findings.append(
                    ReviewFinding(
                        code="broad-except",
                        severity="medium",
                        file_path=diff_file.path,
                        line_number=line.number,
                        message="Avoid broad exception handlers in new code paths.",
                        suggestion="Catch the narrowest expected exception type instead.",
                        excerpt=line.content,
                    ),
                )

    if any(path.startswith("src/") for path in changed_paths) and not any(
        _is_test_path(path) for path in changed_paths
    ):
        findings.append(
            ReviewFinding(
                code="missing-tests",
                severity="medium",
                file_path="tests/",
                line_number=None,
                message="Source changes were detected without accompanying test updates.",
                suggestion="Add or update focused tests that exercise the changed behavior.",
            ),
        )

    return findings


def _security_findings(diff_files: tuple[_DiffFile, ...]) -> list[ReviewFinding]:
    """Return security-focused findings for the diff."""

    findings: list[ReviewFinding] = []
    for diff_file in diff_files:
        for line in diff_file.added_lines:
            content = line.content.strip()
            lowered = content.casefold()
            if any(token in lowered for token in ("api_key =", "secret =", "token =", "password =")):
                findings.append(
                    ReviewFinding(
                        code="hardcoded-secret",
                        severity="high",
                        file_path=diff_file.path,
                        line_number=line.number,
                        message="Do not hardcode credentials or secrets in source code.",
                        suggestion="Load the secret from configuration or the environment instead.",
                        excerpt=line.content,
                    ),
                )
            if "shell=True" in content:
                findings.append(
                    ReviewFinding(
                        code="subprocess-shell-true",
                        severity="high",
                        file_path=diff_file.path,
                        line_number=line.number,
                        message="Avoid subprocess calls that enable the shell for new code paths.",
                        suggestion="Pass argv lists directly and keep shell execution disabled.",
                        excerpt=line.content,
                    ),
                )
            if "yaml.load(" in content:
                findings.append(
                    ReviewFinding(
                        code="unsafe-yaml-load",
                        severity="medium",
                        file_path=diff_file.path,
                        line_number=line.number,
                        message="Use yaml.safe_load when parsing untrusted YAML input.",
                        suggestion="Replace yaml.load with yaml.safe_load.",
                        excerpt=line.content,
                        fixable=True,
                    ),
                )
            if "eval(" in content or "exec(" in content:
                findings.append(
                    ReviewFinding(
                        code="dynamic-eval",
                        severity="high",
                        file_path=diff_file.path,
                        line_number=line.number,
                        message="Avoid dynamic code execution in committed changes.",
                        suggestion="Replace eval or exec with an explicit parser or dispatch table.",
                        excerpt=line.content,
                    ),
                )
            if _looks_like_request_without_timeout(content):
                findings.append(
                    ReviewFinding(
                        code="missing-timeout",
                        severity="medium",
                        file_path=diff_file.path,
                        line_number=line.number,
                        message="HTTP requests should specify an explicit timeout.",
                        suggestion="Pass a timeout keyword argument to the request call.",
                        excerpt=line.content,
                    ),
                )

    return findings


def _build_comment_draft(comment: PullRequestComment) -> CommentDraft:
    """Build a heuristic draft reply for one review comment."""

    body_casefold = comment.body.casefold()
    if "test" in body_casefold:
        draft_reply = "Thanks for the catch. I'll add focused test coverage for this change."
    elif "doc" in body_casefold or "readme" in body_casefold:
        draft_reply = "Good point. I'll update the docs so they match the code change."
    elif "?" in comment.body or body_casefold.startswith(("why", "how", "can", "would")):
        draft_reply = "Thanks for the review. I'll address this feedback and follow up here with the update."
    elif "nit" in body_casefold:
        draft_reply = "Thanks. I'll fold in this cleanup while I update the branch."
    else:
        draft_reply = "Thanks for the review. I'll update the change and follow up here once it's addressed."
    return CommentDraft(
        comment_id=comment.comment_id,
        original_body=comment.body,
        draft_reply=draft_reply,
        path=comment.path,
    )


def _group_findings_by_file(
    findings: list[ReviewFinding] | tuple[ReviewFinding, ...],
) -> dict[str, list[ReviewFinding]]:
    """Group findings by file path."""

    grouped: dict[str, list[ReviewFinding]] = {}
    for finding in findings:
        grouped.setdefault(finding.file_path, []).append(finding)
    return grouped


def _sort_key_for_finding(finding: ReviewFinding) -> tuple[int, str]:
    """Return a descending sort key for line-oriented fixes."""

    return (finding.line_number or 0, finding.code)


def _apply_line_fix(
    lines: list[str],
    finding: ReviewFinding,
    *,
    apply: bool,
) -> tuple[bool, str]:
    """Apply one supported line-oriented fix when possible."""

    if finding.line_number is None:
        return False, "Skipped because the finding does not point to one line."
    if finding.line_number < 1 or finding.line_number > len(lines):
        return False, "Skipped because the referenced line no longer exists."
    if not finding.fixable:
        return False, "Skipped because this finding is not safely auto-fixable."
    if not apply:
        return False, "Preview only; rerun with --apply to make the change."

    line_index = finding.line_number - 1
    current_line = lines[line_index]
    if finding.code == "debug-statement":
        lines.pop(line_index)
        return True, "Removed the debug statement."
    if finding.code == "unsafe-yaml-load" and "yaml.load(" in current_line:
        lines[line_index] = current_line.replace("yaml.load(", "yaml.safe_load(", 1)
        return True, "Replaced yaml.load with yaml.safe_load."
    return False, "Skipped because no safe automatic fix was available."


def _format_findings_summary(count: int) -> str:
    """Return a compact finding-count summary."""

    noun = "finding" if count == 1 else "findings"
    return f"{count} {noun}"


def _is_test_path(path: str) -> bool:
    """Return whether the path looks like a test file."""

    return path.startswith("tests/") or Path(path).stem.startswith("test_")


def _looks_like_request_without_timeout(content: str) -> bool:
    """Return whether the line looks like a network call without a timeout."""

    request_calls = ("requests.get(", "requests.post(", "requests.put(", "requests.patch(", "requests.delete(")
    return any(call in content for call in request_calls) and "timeout=" not in content


__all__ = [
    "AutofixChange",
    "AutofixReport",
    "AutofixService",
    "CommentDraft",
    "CommentManager",
    "CommentReplyResult",
    "PullRequestDiffCache",
    "PullRequestReviewer",
    "ReviewFinding",
    "ReviewReport",
]
