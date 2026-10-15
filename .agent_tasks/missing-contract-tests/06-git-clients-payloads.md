# Missing Contract: Git Clients Payloads

**Severity:** Medium  
**Location:** `src/henchman/git/clients.py`  
**Source types:** `CommandResult`, `GitClient`, `GitHubCliClient`, `PullRequestComment`

## The gap

The `git/clients.py` module defines the low-level git and GitHub CLI interfaces.
`CommandResult` uses a dataclass with fields `argv`, `return_code`, `stdout`,
`stderr`. `PullRequestComment` uses a dataclass with fields `id`, `body`, `path`,
`line`, `created_at`, `author`.

**Neither of these dataclass shapes has a JSON Schema contract.** While
`CommandResult` is mostly internal to the git sub-system, `PullRequestComment`
feeds into `review.py` (which *does* have contract tests for its own dataclasses).

## What's consumed

- `CommandResult` is consumed by `GitClient` and `GitHubCliClient` callers
  throughout `git/workflow.py` and `git/review.py`.
- `PullRequestComment` is consumed by `review.py`'s `CommentManager`.

## Recommended contract schema

Create `tests/contracts/schemas/cli/pull_request_comment.json` covering the
comment dataclass shape. The `CommandResult` shape is a lower priority but
could be validated with `tests/contracts/schemas/cli/command_result.json`.

## Recommended contract test

Add to `test_cli_boundary_contracts.py`:

```python
def test_git_payloads_match_contracts(contract_suite):
    comment = PullRequestComment(
        id=42,
        body="Please fix this",
        path="src/main.py",
        line=10,
        created_at="2026-04-24T12:00:00Z",
        author="reviewer-bot",
    )
    assert_contract_matches(
        payload=asdict(comment),
        schema_name="cli/pull_request_comment",
        contract_suite=contract_suite,
    )
```

## Priority

Medium — `PullRequestComment` shape is already an implicit contract with `review.py`.
