#!/usr/bin/env bash
# auto-improve.sh — Four Lenses of Failure: find one real bug, TDD-fix it, commit.
set -euo pipefail

alias pytest='prlimit --as=16G --rss=16G python -m pytest'

# Limit memory usage to 16GB
ulimit -v 16777216  # 16GB in KB
# Temporarily disable nounset — conda activation scripts use unbound vars
set +u
source "/home/matthew/anaconda3/etc/profile.d/conda.sh"
source "/home/matthew/.bashrc"
conda activate base
set -u

export DEEPSEEK_API_KEY="${DEEPSEEK_API_KEY:?DEEPSEEK_API_KEY must be set}"

WORKDIR="/home/matthew/mlg-cli"
LOGFILE="$WORKDIR/.agent_tasks/auto-improve/last-run.log"
TIMESTAMP=$(date -u +"%Y-%m-%dT%H:%M:%SZ")

cd "$WORKDIR"

# Ensure log directory exists
mkdir -p "$(dirname "$LOGFILE")"

echo "[$TIMESTAMP] Starting Four Lenses bug-hunt run..." | tee "$LOGFILE"

# ---------------------------------------------------------------------------
# Run code smell detector — feeds context to the agent
# ---------------------------------------------------------------------------
SMELL_REPORT="$WORKDIR/.agent_tasks/auto-improve/smell-report.md"
echo "Running code smell detector..." | tee -a "$LOGFILE"
python -m scripts.smell_detector src/henchman --skip-ruff -o "$SMELL_REPORT" 2>&1 | tee -a "$LOGFILE"

# ---------------------------------------------------------------------------
# Extract the lowest-graded (worst) file from the "Files Ranked by Quality" table
# The table has format: | Rank | File | Grade | Score | ...
# Rank 1 = worst file. We grab the file path from that row.
# ---------------------------------------------------------------------------
TARGET_FILE=$(grep -E '^\| *1 \|' "$SMELL_REPORT" | head -1 | awk -F'|' '{gsub(/^[ \t]+|[ \t]+$/, "", $3); print $3}')

if [ -z "$TARGET_FILE" ]; then
  echo "[$TIMESTAMP] Could not extract target file from smell report. Falling back to full report." | tee -a "$LOGFILE"
  TARGET_FILE_DISPLAY="<unknown — read the smell report and pick the lowest-scored file>"
else
  TARGET_FILE_DISPLAY="src/henchman/$TARGET_FILE"
  echo "[$TIMESTAMP] Targeting lowest-graded file: $TARGET_FILE_DISPLAY" | tee -a "$LOGFILE"
fi

# ---------------------------------------------------------------------------
# Generate a slug for the .agent_tasks/ stub from the target file
# e.g. "agents/orchestrator.py" → "four-lenses-agents-orchestrator"
# ---------------------------------------------------------------------------
if [ -n "$TARGET_FILE" ]; then
  TASK_SLUG="four-lenses-$(echo "$TARGET_FILE" | sed 's|/|-|g; s|\.py$||')"
else
  TASK_SLUG="four-lenses-$(date +%Y%m%d-%H%M%S)"
fi
TASK_DIR="$WORKDIR/.agent_tasks/$TASK_SLUG"
mkdir -p "$TASK_DIR"

# ---------------------------------------------------------------------------
# The Prompt — Four Lenses of Failure, TDD, single bug focus
# ---------------------------------------------------------------------------
read -r -d '' PROMPT <<'PROMPT_EOF' || true
You are "The Bug Whisperer," a Principal Software Engineer known for fixing
systems that everyone else gave up on. You don't just look for syntax errors —
you look for logical inconsistencies, state leakage, and architectural fragility.

## TARGET FILE
__TARGET_FILE__

Read the smell report at .agent_tasks/auto-improve/smell-report.md for context,
then read the TARGET FILE and its tests.

## Your Objective
Deconstruct the TARGET FILE using the **Four Lenses of Failure**, identify
exactly **ONE real bug** in core functionality, and fix it using strict TDD.

### Phase 1: The Intent vs. Reality Check
- **Logic Gaps**: Where does the code assume a "happy path"? Identify silent
  failures (e.g., try/except that swallows errors without logging).
- **Type Safety**: Where could an unexpected `None`, `list`, or `dict` crash
  a downstream function?

### Phase 2: State & Side Effects (The Entropy Audit)
- **Shared State**: Identify mutable variables that could be modified elsewhere.
- **Immutability**: Check if the code accidentally mutates inputs (e.g.,
  modifying a list argument) which could break callers.
- **Scope Creep**: Functions doing too many things, making them impossible to
  unit test properly.

### Phase 3: Performance & Resource Management
- **Algorithmic Efficiency**: O(n²) that could be O(n) with better structures.
- **Resource Leaks**: Unclosed handles, large copies in memory.

### Phase 4: The Forensic Refactor
- **The Fix**: Provide a minimal, surgical fix for the ONE bug you found.
- **The "Unit of Doom"**: Write a pytest test that FAILS on the original code
  and PASSES after your fix.

## Strict Workflow (TDD — you MUST follow this order)

1. **Analyze**: Read the target file through all four lenses. Pick the single
   highest-priority bug — something that affects core functionality, not style.

2. **Document the stub**: Create/update the file:
   `.agent_tasks/__TASK_SLUG__/README.md`
   with this structure:
   ```markdown
   # Four Lenses Bug Report: __TARGET_FILE__
   ## Date: <ISO timestamp>
   ## Bug Summary
   <1-2 sentence description of the bug>
   ## Lens
   <Which of the 4 lenses revealed it>
   ## Expected vs. Observed
   | Expected Behavior | Observed Risk |
   |---|---|
   | ... | ... |
   ## Root Cause
   <Technical explanation>
   ## Fix Plan
   <What you will change and where>
   ## Status: IN PROGRESS
   ```

3. **Write the failing test FIRST** (Unit of Doom):
   - Add a new test to the appropriate `tests/` file (or create one).
   - The test MUST demonstrate the bug — it should FAIL before your fix.
   - Run: `python -m pytest tests/<test_file> -x -q --tb=short` to confirm it fails.

4. **Implement the minimal fix**:
   - Change ONLY what is necessary to fix the bug.
   - Do NOT refactor surrounding code, add features, or "improve" unrelated things.

5. **Verify ALL tests pass**:
   - Run: `python -m pytest tests/ -x -q --tb=short`
   - If anything fails, fix it. Do NOT leave the codebase broken.

6. **Update the stub**: Change `## Status: IN PROGRESS` to `## Status: FIXED`
   and add a `## Files Changed` section listing every file you modified.

## Critical Rules
- Fix exactly ONE bug. Not zero. Not two.
- The bug must be in core functionality (not docs, not style, not naming).
- TDD is mandatory: failing test FIRST, then fix, then green suite.
- Keep changes minimal and surgical.
- Do NOT modify this script or the auto-improve infrastructure.
- ALL tests must pass before you finish. Fix forward if anything breaks.
PROMPT_EOF

# Substitute placeholders
PROMPT="${PROMPT//__TARGET_FILE__/$TARGET_FILE_DISPLAY}"
PROMPT="${PROMPT//__TASK_SLUG__/$TASK_SLUG}"

# ---------------------------------------------------------------------------
# Run Henchman in headless mode with auto-approve
# ---------------------------------------------------------------------------
echo "Running Henchman..." | tee -a "$LOGFILE"
henchman chat --yes -p "$PROMPT" 2>&1 | tee -a "$LOGFILE"

HENCHMAN_EXIT=${PIPESTATUS[0]}

if [ "$HENCHMAN_EXIT" -eq 2 ]; then
  echo "[$TIMESTAMP] Agent completed without performing any actions. Nothing to do." | tee -a "$LOGFILE"
  exit 0
fi

if [ "$HENCHMAN_EXIT" -ne 0 ]; then
  echo "[$TIMESTAMP] Henchman exited with code $HENCHMAN_EXIT" | tee -a "$LOGFILE"
  exit "$HENCHMAN_EXIT"
fi

# ---------------------------------------------------------------------------
# Early exit if no files were changed
# ---------------------------------------------------------------------------
if git diff --quiet HEAD 2>/dev/null; then
  echo "[$TIMESTAMP] No file changes detected after agent run. Nothing to commit." | tee -a "$LOGFILE"
  exit 0
fi

# ---------------------------------------------------------------------------
# Post-fix test gate: run pytest and let the agent fix failures
# ---------------------------------------------------------------------------
MAX_FIX_ATTEMPTS=3
ATTEMPT=0

while true; do
  echo "[$TIMESTAMP] Running pytest to verify tests pass..." | tee -a "$LOGFILE"
  if /usr/bin/prlimit --as=17179869184 --rss=17179869184 python -m pytest tests/ -x -q --tb=short 2>&1 | tee -a "$LOGFILE"; then
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

  FIX_PROMPT='Tests are failing after your bug fix.

Your task:
1. Run: python -m pytest tests/ -x -q --tb=short
2. Read the failures carefully.
3. Fix ONLY the failing tests or the code that caused them to fail.
   Do NOT make any other improvements — just restore a green test suite.
4. Re-run the tests to confirm they pass before finishing.

Important constraints:
- Fix the minimum necessary to make tests pass.
- Do NOT revert the bug fix — fix forward.
- If the fix itself is fundamentally broken, revert ONLY that change.'

  henchman chat --yes -p "$FIX_PROMPT" 2>&1 | tee -a "$LOGFILE"
  FIX_EXIT=${PIPESTATUS[0]}

  if [ "$FIX_EXIT" -ne 0 ]; then
    echo "[$TIMESTAMP] Henchman fix attempt exited with code $FIX_EXIT" | tee -a "$LOGFILE"
  fi
done

# ---------------------------------------------------------------------------
# Stage all changes and commit
# ---------------------------------------------------------------------------
if git diff --quiet HEAD 2>/dev/null; then
  echo "[$TIMESTAMP] No changes were made. Nothing to commit." | tee -a "$LOGFILE"
  exit 0
fi

echo "Committing changes..." | tee -a "$LOGFILE"
git add -A

SUMMARY=""
if [ -f "$TASK_DIR/README.md" ]; then
  SUMMARY=$(grep -A2 '## Bug Summary' "$TASK_DIR/README.md" | tail -1 || true)
fi

COMMIT_MSG="fix(four-lenses): $TASK_SLUG

${SUMMARY:-Automated bug fix via Four Lenses of Failure analysis}

Target: $TARGET_FILE_DISPLAY
Automated by scripts/auto-improve.sh at $TIMESTAMP"

git commit -m "$COMMIT_MSG" | tee -a "$LOGFILE"

echo "[$TIMESTAMP] Auto-improve complete." | tee -a "$LOGFILE"
