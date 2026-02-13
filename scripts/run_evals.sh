#!/bin/bash
# Run behavioral evaluations for henchman-ai
#
# Usage:
#   ./scripts/run_evals.sh         # Run ALWAYS_PASSES only (CI-safe)
#   ./scripts/run_evals.sh --ci    # Same as above
#   ./scripts/run_evals.sh --all   # Run all evals including flaky ones
#   ./scripts/run_evals.sh --nightly # Run all evals 3 times for stats

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_ROOT"

# Default: CI mode (only ALWAYS_PASSES)
MODE="ci"
RUNS=1

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --ci)
            MODE="ci"
            shift
            ;;
        --all)
            MODE="all"
            shift
            ;;
        --nightly)
            MODE="nightly"
            RUNS=3
            shift
            ;;
        *)
            echo "Unknown option: $1"
            echo "Usage: $0 [--ci|--all|--nightly]"
            exit 1
            ;;
    esac
done

echo "=== Henchman-AI Behavioral Evals ==="
echo "Mode: $MODE"
echo ""

# Create logs directory
mkdir -p evals/logs

case $MODE in
    ci)
        echo "Running ALWAYS_PASSES evals (CI-safe)..."
        pytest evals/ -m "always_passes" -v --tb=short
        ;;
    all)
        echo "Running all evals..."
        RUN_ALL_EVALS=1 pytest evals/ -v --tb=short
        ;;
    nightly)
        echo "Running nightly evals ($RUNS runs each)..."
        TOTAL_PASSED=0
        TOTAL_FAILED=0
        
        for i in $(seq 1 $RUNS); do
            echo ""
            echo "=== Run $i of $RUNS ==="
            if RUN_ALL_EVALS=1 pytest evals/ -v --tb=line 2>&1; then
                ((TOTAL_PASSED++)) || true
            else
                ((TOTAL_FAILED++)) || true
            fi
        done
        
        echo ""
        echo "=== Nightly Summary ==="
        echo "Passed runs: $TOTAL_PASSED / $RUNS"
        echo "Failed runs: $TOTAL_FAILED / $RUNS"
        PASS_RATE=$((TOTAL_PASSED * 100 / RUNS))
        echo "Pass rate: $PASS_RATE%"
        ;;
esac

echo ""
echo "=== Evals Complete ==="
