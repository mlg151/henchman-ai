#!/usr/bin/env bash
# auto-improve.sh — Run Henchman to make one codebase improvement, then commit.
set -euo pipefail

WORKDIR="/home/matthew/mlg-cli"
LOGFILE="$WORKDIR/.agent_tasks/auto-improve/last-run.log"
TIMESTAMP=$(date -u +"%Y-%m-%dT%H:%M:%SZ")

cd "$WORKDIR"

# Ensure log directory exists
mkdir -p "$(dirname "$LOGFILE")"

echo "[$TIMESTAMP] Starting auto-improve run..." | tee "$LOGFILE"

# # Bail out if the working tree is dirty (avoid mixing unrelated changes)
# if ! git diff --quiet HEAD 2>/dev/null; then
#   echo "ERROR: Working tree has uncommitted changes. Commit or stash first." | tee -a "$LOGFILE"
#   exit 1
# fi

PROMPT='You are running in an automated improvement cycle on the Henchman-AI codebase.

Your task:
1. Pick ONE small, valuable improvement to make to the codebase. Examples:
   - Fix a TODO/FIXME comment
   - Improve a docstring or type hint
   - Add a missing edge-case test
   - Refactor a small piece of duplicated code
   - Improve an error message
   - Fix a minor bug
   Do NOT attempt large refactors or multi-file rewrites.

2. Implement the change. Make sure tests still pass by running: ./scripts/ci.sh

3. Write a short summary of what you changed and why into the file
   .agent_tasks/auto-improve/last-improvement.md (create or overwrite it).
   Include the date/time, files changed, and rationale.

Important constraints:
- Only make ONE improvement per run.
- Keep changes minimal and focused.
- Ensure all CI checks pass before finishing.
- Do NOT modify this prompt or the auto-improve script itself.'

# Run Henchman in headless mode with auto-approve
echo "Running Henchman..." | tee -a "$LOGFILE"
henchman chat --yes -p "$PROMPT" 2>&1 | tee -a "$LOGFILE"

HENCHMAN_EXIT=${PIPESTATUS[0]}

if [ "$HENCHMAN_EXIT" -ne 0 ]; then
  echo "[$TIMESTAMP] Henchman exited with code $HENCHMAN_EXIT" | tee -a "$LOGFILE"
  exit "$HENCHMAN_EXIT"
fi

# Check if there are any changes to commit
if git diff --quiet HEAD 2>/dev/null; then
  echo "[$TIMESTAMP] No changes were made. Nothing to commit." | tee -a "$LOGFILE"
  exit 0
fi

# Stage all changes and commit
echo "Committing changes..." | tee -a "$LOGFILE"
git add -A
SUMMARY=""
if [ -f "$WORKDIR/.agent_tasks/auto-improve/last-improvement.md" ]; then
  SUMMARY=$(head -5 "$WORKDIR/.agent_tasks/auto-improve/last-improvement.md" | tail -4)
fi

COMMIT_MSG="chore(auto-improve): automated codebase improvement

${SUMMARY}

Automated by scripts/auto-improve.sh at $TIMESTAMP"

git commit -m "$COMMIT_MSG" | tee -a "$LOGFILE"

echo "[$TIMESTAMP] Auto-improve complete." | tee -a "$LOGFILE"
