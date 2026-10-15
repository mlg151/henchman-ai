"""Git and pull-request integration services."""

from henchman.git.clients import CommandExecutionError, CommandResult, GitClient, GitHubCliClient
from henchman.git.github_app import (
    GitHubAppInstallRecord,
    GitHubAppService,
    GitHubWebhookResult,
    GitHubWebhookService,
)
from henchman.git.review import (
    AutofixChange,
    AutofixReport,
    AutofixService,
    CommentDraft,
    CommentManager,
    CommentReplyResult,
    PullRequestDiffCache,
    PullRequestReviewer,
    ReviewFinding,
    ReviewReport,
)
from henchman.git.workflow import (
    BranchInfo,
    BranchManager,
    BranchOperation,
    CommitAssistant,
    CommitSuggestion,
    PullRequestWorkflow,
    PullRequestWorkflowResult,
)

__all__ = [
    "AutofixChange",
    "AutofixReport",
    "AutofixService",
    "BranchInfo",
    "BranchManager",
    "BranchOperation",
    "CommandExecutionError",
    "CommandResult",
    "CommentDraft",
    "CommentManager",
    "CommentReplyResult",
    "CommitAssistant",
    "CommitSuggestion",
    "GitClient",
    "GitHubAppInstallRecord",
    "GitHubAppService",
    "GitHubCliClient",
    "GitHubWebhookResult",
    "GitHubWebhookService",
    "PullRequestDiffCache",
    "PullRequestReviewer",
    "PullRequestWorkflow",
    "PullRequestWorkflowResult",
    "ReviewFinding",
    "ReviewReport",
]
