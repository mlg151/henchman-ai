#!/usr/bin/env bash
# auto-improve.sh — Run Henchman to make one codebase improvement, then commit.
set -euo pipefail

# Activate the base conda environment
# Temporarily disable nounset — conda activation scripts use unbound vars
set +u
source "/home/matthew/anaconda3/etc/profile.d/conda.sh"
conda activate base
set -u

export DEEPSEEK_API_KEY="sk-999d210dbd284fe8be163d625166ea64"

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

# PROMPT='You are running in an automated improvement cycle on the Henchman-AI codebase.

# Your task:
# 1. Pick ONE small, valuable improvement to make to the codebase. Examples:
#    - Fix a TODO/FIXME comment
#    - Improve a docstring or type hint
#    - Add a missing edge-case test
#    - Refactor a small piece of duplicated code
#    - Improve an error message
#    - Fix a minor bug
#    Do NOT attempt large refactors or multi-file rewrites.
#    DO check .agent_tasks/auto-improve/last-improvement.md for what was changed last time to avoid repeating the same improvement.

# 2. Implement the change. Make sure tests still pass by running: ./scripts/ci.sh

# 3. Write a short summary of what you changed and why into the file
#    .agent_tasks/auto-improve/last-improvement.md (create or overwrite it).
#    Include the date/time, files changed, and rationale.

# Important constraints:
# - Only make ONE improvement per run.
# - Keep changes minimal and focused.
# - Ensure all CI checks pass before finishing.
# - Do NOT modify this prompt or the auto-improve script itself.'

PROMPT='You are an Expert Extreme Programming (XP) Refactoring Agent. Your primary objective is to execute Continuous Refactoring on the provided codebase. You will improve the internal structure, readability, maintainability, and performance of the code without altering its external behavior or breaking existing functionality.

Core XP Philosophy:

    YAGNI (You Are not Gonna Need It): Remove dead code and do not add speculative features or abstractions.

    Once and Only Once (DRY): Aggressively eliminate duplicated logic.

    Simplicity: The design should be as simple as possible to pass the current tests.

    Intention-Revealing Code: Rename variables, functions, and classes to perfectly describe their purpose.

Tech-Stack Specific Guidelines:

    Python: Enforce PEP 8 standards. Use type hinting consistently. Prefer list comprehensions and generator expressions where they enhance readability, but extract complex lambda functions into named def functions.

Execution Steps:

    Code Smell Analysis: Scan the provided code for standard code smells (Long Method, Large Class, Primitive Obsession, Feature Envy, Magic Numbers, Deep Nesting).

    Determine the Refactoring Pattern: Select the appropriate Martin Fowler refactoring technique (e.g., Extract Method, Replace Conditional with Polymorphism, Introduce Parameter Object, Rename Method).

    Safety Check: Ensure the refactoring relies on standard testing paradigms. Do not change public API signatures unless explicitly instructed, as this breaks downstream contracts.

    Execution: Rewrite the code.

Output Format:
Whenever you are provided with a code snippet to refactor, you must respond strictly in the following format:

    Identified Smells: (A brief bulleted list of the code smells found)

    Refactoring Strategy: (The specific patterns applied, e.g., "Extracted nested conditional logic into _calculate_monthly_aggregates()")

    Refactored Code: (The complete, refactored code block)

    Testing Implications: (A 1-2 sentence note on what existing unit tests might need updating, or what new edge cases should be tested based on the structural change)
    
Please pick one improvement to make to the codebase, implement it, and ensure all tests pass. DO check .agent_tasks/auto-improve/last-improvement.md for what was changed last time to avoid repeating the same improvement.

ALL TESTS. EVEN IF YOU THINK THE FAILURE IS UNRELATED TO YOUR CHANGE, FIX IT. DO NOT LEAVE THE CODE IN A BROKEN STATE!'

# Run Henchman in headless mode with auto-approve
echo "Running Henchman..." | tee -a "$LOGFILE"
henchman chat --yes -p "$PROMPT" 2>&1 | tee -a "$LOGFILE"

HENCHMAN_EXIT=${PIPESTATUS[0]}

if [ "$HENCHMAN_EXIT" -ne 0 ]; then
  echo "[$TIMESTAMP] Henchman exited with code $HENCHMAN_EXIT" | tee -a "$LOGFILE"
  exit "$HENCHMAN_EXIT"
fi

# ---------------------------------------------------------------------------
# Post-improvement test gate: run pytest and let the agent fix failures
# ---------------------------------------------------------------------------
MAX_FIX_ATTEMPTS=3
ATTEMPT=0

while true; do
  echo "[$TIMESTAMP] Running pytest to verify tests pass..." | tee -a "$LOGFILE"
  if python -m pytest tests/ -x -q --tb=short 2>&1 | tee -a "$LOGFILE"; then
    echo "[$TIMESTAMP] All tests passed." | tee -a "$LOGFILE"
    break
  fi

  ATTEMPT=$((ATTEMPT + 1))
  if [ "$ATTEMPT" -ge "$MAX_FIX_ATTEMPTS" ]; then
    echo "[$TIMESTAMP] Tests still failing after $MAX_FIX_ATTEMPTS fix attempts. Reverting changes." | tee -a "$LOGFILE"
    git checkout -- .
    git clean -fd
    exit 1
  fi

  echo "[$TIMESTAMP] Tests failed. Asking Henchman to fix (attempt $ATTEMPT/$MAX_FIX_ATTEMPTS)..." | tee -a "$LOGFILE"

  FIX_PROMPT='Tests are failing after your last auto-improve change.

Your task:
1. Run: python -m pytest tests/ -x -q --tb=short
2. Read the failures carefully.
3. Fix ONLY the failing tests or the code that caused them to fail.
   Do NOT make any other improvements — just restore a green test suite.
4. Re-run the tests to confirm they pass before finishing.

Important constraints:
- Fix the minimum necessary to make tests pass.
- Do NOT revert the improvement — fix forward.
- If the improvement itself is fundamentally broken, revert ONLY that change.'

  copilot --yolo -p "$FIX_PROMPT" 2>&1 | tee -a "$LOGFILE"
  FIX_EXIT=${PIPESTATUS[0]}

  if [ "$FIX_EXIT" -ne 0 ]; then
    echo "[$TIMESTAMP] Henchman fix attempt exited with code $FIX_EXIT" | tee -a "$LOGFILE"
    # Continue to next iteration — the pytest check at top of loop will re-evaluate
  fi
done

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
