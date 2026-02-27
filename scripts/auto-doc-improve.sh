#!/usr/bin/env bash
# auto-doc-improve.sh — Run Henchman to make one documentation improvement, then commit.
set -euo pipefail

# Activate the base conda environment
# Temporarily disable nounset — conda activation scripts use unbound vars
set +u
source "/home/matthew/anaconda3/etc/profile.d/conda.sh"
conda activate base
set -u

export DEEPSEEK_API_KEY="${DEEPSEEK_API_KEY:?DEEPSEEK_API_KEY must be set}"

WORKDIR="/home/matthew/mlg-cli"
LOGFILE="$WORKDIR/.agent_tasks/auto-doc-improve/last-run.log"
TIMESTAMP=$(date -u +"%Y-%m-%dT%H:%M:%SZ")

cd "$WORKDIR"

# Ensure log / output directories exist
mkdir -p "$(dirname "$LOGFILE")"

echo "[$TIMESTAMP] Starting auto-doc-improve run..." | tee "$LOGFILE"

# ---------------------------------------------------------------------------
# Prompt for the documentation improvement agent
# ---------------------------------------------------------------------------
PROMPT='You are an Expert Technical Documentation Improvement Agent. Your primary objective is to improve the quality, accuracy, and completeness of the project documentation without altering source code behavior.

Core Documentation Principles:

    ACCURACY: Documentation must match the actual code. Fix stale class names, outdated tool lists, wrong API signatures.

    COMPLETENESS: All public APIs should be documented. All doc pages should be reachable via navigation.

    CONSISTENCY: GitHub URLs, install commands, coverage thresholds, and terminology must be uniform across all files.

    DISCOVERABILITY: Pages must be in the mkdocs nav. Links must resolve. Mermaid diagrams must render.

Scope of Documentation:

    Markdown pages: docs/*.md, README.md, CONTRIBUTING.md, CHANGELOG.md, RELEASE_CHECKLIST.md
    MkDocs config: mkdocs.yml (nav, plugins, extensions, theme)
    Python docstrings: Google-style docstrings on all public classes, methods, and functions in src/henchman/
    Cross-references: Internal links between .md files must resolve

Execution Steps:

    1. Read the doc smell report (referenced below) to identify the highest-priority issue.
    2. Pick ONE documentation improvement to make. Focus on the highest-severity smell first.
    3. Implement the fix:
       - For orphaned pages: Add them to mkdocs.yml nav
       - For stale content: Update tool lists, provider tables, class names to match source code
       - For broken links: Fix link targets or create missing files
       - For missing docstrings: Add Google-style docstrings with Args/Returns/Raises sections
       - For config issues: Fix mkdocs.yml (mermaid config, plugins, etc.)
       - For consistency errors: Standardise URLs, thresholds, install commands across files
    4. Verify your fix makes sense and does not break other documentation.
    5. Write a summary of what you changed to .agent_tasks/auto-doc-improve/last-improvement.md

Output Format:
After completing the fix, write to .agent_tasks/auto-doc-improve/last-improvement.md:
    - Date/time of the improvement
    - Files changed
    - Smell category that was addressed
    - Brief rationale for the change
    - What to verify

Important constraints:
- Only make ONE improvement per run.
- Keep changes minimal and focused.
- Do NOT modify source code behavior — only documentation, docstrings, and config.
- Do NOT modify the auto-doc-improve script itself.
- Check .agent_tasks/auto-doc-improve/last-improvement.md for what was changed last time to avoid repeating.

ALL DOCUMENTATION MUST BE ACCURATE. If you update a doc page, verify the information matches the actual source code.'

# ---------------------------------------------------------------------------
# Run documentation smell detector
# ---------------------------------------------------------------------------
DOC_SMELL_REPORT="$WORKDIR/.agent_tasks/auto-doc-improve/doc-smell-report.md"
echo "Running documentation smell detector..." | tee -a "$LOGFILE"
python -m scripts.doc_smell_detector "$WORKDIR" -o "$DOC_SMELL_REPORT" 2>&1 | tee -a "$LOGFILE"

# Append the doc smell report reference to the prompt.
PROMPT="$PROMPT"$'\n\nRefer to the documentation smell report for prioritised improvement targets: @'"$DOC_SMELL_REPORT"

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
# Post-improvement verification gate: mkdocs build + re-run detector
# ---------------------------------------------------------------------------
MAX_FIX_ATTEMPTS=3
ATTEMPT=0

while true; do
  echo "[$TIMESTAMP] Running mkdocs build to verify documentation..." | tee -a "$LOGFILE"

  # Try mkdocs build (non-strict first, since strict may fail on external deps)
  BUILD_OK=true
  if command -v mkdocs &>/dev/null; then
    if ! mkdocs build --clean 2>&1 | tee -a "$LOGFILE"; then
      BUILD_OK=false
    fi
  else
    echo "[$TIMESTAMP] mkdocs not installed, skipping build verification." | tee -a "$LOGFILE"
  fi

  # Also re-run the detector to verify score improved
  echo "[$TIMESTAMP] Re-running doc smell detector to verify improvement..." | tee -a "$LOGFILE"
  python -m scripts.doc_smell_detector "$WORKDIR" --skip-docstrings -f json 2>&1 | tail -1 | tee -a "$LOGFILE"

  if [ "$BUILD_OK" = true ]; then
    echo "[$TIMESTAMP] Verification passed." | tee -a "$LOGFILE"
    break
  fi

  ATTEMPT=$((ATTEMPT + 1))
  if [ "$ATTEMPT" -ge "$MAX_FIX_ATTEMPTS" ]; then
    echo "[$TIMESTAMP] Verification still failing after $MAX_FIX_ATTEMPTS fix attempts. Reverting changes." | tee -a "$LOGFILE"
    git checkout -- .
    git clean -fd
    exit 1
  fi

  echo "[$TIMESTAMP] Build failed. Asking Henchman to fix (attempt $ATTEMPT/$MAX_FIX_ATTEMPTS)..." | tee -a "$LOGFILE"

  FIX_PROMPT='The mkdocs build is failing after your last documentation improvement.

Your task:
1. Read the mkdocs build output above carefully.
2. Fix ONLY the issue causing the build failure.
   Common causes: broken nav references, invalid YAML, missing referenced files.
3. Re-run: mkdocs build --clean
4. Verify it passes before finishing.

Important constraints:
- Fix the minimum necessary to make the build pass.
- Do NOT revert the documentation improvement — fix forward.
- If the improvement itself is fundamentally broken, revert ONLY that change.'

  /home/matthew/.local/bin/copilot --yolo -p "$FIX_PROMPT" 2>&1 | tee -a "$LOGFILE"
  FIX_EXIT=${PIPESTATUS[0]}

  if [ "$FIX_EXIT" -ne 0 ]; then
    echo "[$TIMESTAMP] Fix attempt exited with code $FIX_EXIT" | tee -a "$LOGFILE"
  fi
done

# ---------------------------------------------------------------------------
# Stage and commit
# ---------------------------------------------------------------------------
if git diff --quiet HEAD 2>/dev/null; then
  echo "[$TIMESTAMP] No changes were made. Nothing to commit." | tee -a "$LOGFILE"
  exit 0
fi

echo "Committing changes..." | tee -a "$LOGFILE"
git add -A
SUMMARY=""
if [ -f "$WORKDIR/.agent_tasks/auto-doc-improve/last-improvement.md" ]; then
  SUMMARY=$(head -5 "$WORKDIR/.agent_tasks/auto-doc-improve/last-improvement.md" | tail -4)
fi

COMMIT_MSG="docs(auto-improve): automated documentation improvement

${SUMMARY}

Automated by scripts/auto-doc-improve.sh at $TIMESTAMP"

git commit -m "$COMMIT_MSG" | tee -a "$LOGFILE"

echo "[$TIMESTAMP] Done." | tee -a "$LOGFILE"
