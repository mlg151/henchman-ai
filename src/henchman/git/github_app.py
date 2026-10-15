"""GitHub App installation and webhook helpers."""

from __future__ import annotations

import hashlib
import hmac
import json
import webbrowser
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from henchman.config.paths import resolve_project_settings_path
from henchman.git.review import PullRequestDiffCache


@dataclass(frozen=True, slots=True)
class GitHubAppInstallRecord:
    """Persisted local metadata for GitHub App setup."""

    app_url: str
    repo_slug: str | None
    installation_id: int | None
    webhook_secret_env: str
    metadata_path: Path

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-serializable representation."""

        return {
            "app_url": self.app_url,
            "repo_slug": self.repo_slug,
            "installation_id": self.installation_id,
            "webhook_secret_env": self.webhook_secret_env,
            "metadata_path": str(self.metadata_path),
        }


@dataclass(frozen=True, slots=True)
class GitHubWebhookResult:
    """Structured result from handling one GitHub webhook event."""

    event_name: str
    action: str | None
    repository: str | None
    pull_request_number: int | None
    signature_valid: bool
    cache_invalidated: bool

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-serializable representation."""

        return {
            "event_name": self.event_name,
            "action": self.action,
            "repository": self.repository,
            "pull_request_number": self.pull_request_number,
            "signature_valid": self.signature_valid,
            "cache_invalidated": self.cache_invalidated,
        }


class GitHubAppService:
    """Persist one local GitHub App setup record."""

    def __init__(
        self,
        project_root: Path | None = None,
        *,
        url_opener: Callable[[str], bool] | None = None,
    ) -> None:
        """Initialize the service."""

        self._project_root = (project_root or Path.cwd()).resolve()
        self._url_opener = url_opener or webbrowser.open

    def install(
        self,
        *,
        app_url: str,
        repo_slug: str | None = None,
        installation_id: int | None = None,
        webhook_secret_env: str = "HENCHMAN_GITHUB_WEBHOOK_SECRET",
        open_browser: bool = False,
    ) -> GitHubAppInstallRecord:
        """Persist GitHub App setup details and optionally open the install URL."""

        if not app_url.strip():
            raise ValueError("A GitHub App installation URL is required.")

        metadata_path = resolve_project_settings_path(self._project_root) / "github" / "app_installation.json"
        metadata_path.parent.mkdir(parents=True, exist_ok=True)
        record = GitHubAppInstallRecord(
            app_url=app_url,
            repo_slug=repo_slug,
            installation_id=installation_id,
            webhook_secret_env=webhook_secret_env,
            metadata_path=metadata_path,
        )
        metadata_path.write_text(json.dumps(record.to_dict(), sort_keys=True, indent=2), encoding="utf-8")
        if open_browser:
            self._url_opener(app_url)
        return record


class GitHubWebhookService:
    """Verify and handle GitHub webhook payloads."""

    def handle_event(
        self,
        *,
        event_name: str,
        payload: bytes,
        signature: str | None,
        secret: str,
        diff_cache: PullRequestDiffCache | None = None,
    ) -> GitHubWebhookResult:
        """Validate one webhook payload and invalidate PR diff cache when needed."""

        signature_valid = _verify_signature(payload=payload, signature=signature, secret=secret)
        if not signature_valid:
            return GitHubWebhookResult(
                event_name=event_name,
                action=None,
                repository=None,
                pull_request_number=None,
                signature_valid=False,
                cache_invalidated=False,
            )

        try:
            payload_data = json.loads(payload.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ValueError("Invalid GitHub webhook payload.") from exc
        if not isinstance(payload_data, dict):
            raise ValueError("Invalid GitHub webhook payload.")

        action = payload_data.get("action") if isinstance(payload_data.get("action"), str) else None
        pr_number = payload_data.get("number") if isinstance(payload_data.get("number"), int) else None
        repository = None
        repository_payload = payload_data.get("repository")
        if isinstance(repository_payload, dict):
            full_name = repository_payload.get("full_name")
            repository = full_name if isinstance(full_name, str) else None

        cache_invalidated = False
        if (
            diff_cache is not None
            and event_name == "pull_request"
            and repository is not None
            and pr_number is not None
            and action in {"opened", "synchronize", "reopened", "closed"}
        ):
            cache_invalidated = diff_cache.invalidate(pr_number=pr_number, repo_slug=repository)

        return GitHubWebhookResult(
            event_name=event_name,
            action=action,
            repository=repository,
            pull_request_number=pr_number,
            signature_valid=True,
            cache_invalidated=cache_invalidated,
        )


def _verify_signature(*, payload: bytes, signature: str | None, secret: str) -> bool:
    """Return whether the GitHub HMAC SHA256 signature is valid."""

    if signature is None or not signature.startswith("sha256="):
        return False
    digest = hmac.new(secret.encode("utf-8"), payload, hashlib.sha256).hexdigest()
    return hmac.compare_digest(signature.removeprefix("sha256="), digest)


__all__ = [
    "GitHubAppInstallRecord",
    "GitHubAppService",
    "GitHubWebhookResult",
    "GitHubWebhookService",
]
