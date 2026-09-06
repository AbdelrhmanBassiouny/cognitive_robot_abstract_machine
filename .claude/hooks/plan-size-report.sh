#!/bin/bash
set -euo pipefail

# Reports every plan on the personal-notes branch against the size budget -
# how many items its plan.yaml declares, how many lines its plan.yaml and
# roadmap.md hold together, and which half of the budget it is over.
#
# Usage (from anywhere):
#   "$CLAUDE_PROJECT_DIR/.claude/hooks/plan-size-report.sh"
#
# Takes no arguments: the budget is fixed (see plan_size_budget.py's
# SizeBudget) and every plan is measured, since the question the report
# answers is which plans are approaching it, not how one plan is doing.
#
# Reports only. Nothing here refuses a save, so a plan already over the budget
# is still saveable while it waits to be split.
#
# The budget, the measurement and the report's wording all live in
# plan_size_budget.py rather than inline here - so this script never carries
# its own copy of numbers or text the test suite also has to check against.
#
# Reads the notes branch off FETCH_HEAD, writing each plan's two files into a
# scratch directory for the report to measure. Never checks anything out and
# never touches your current branch or working tree.
#
# Requires python3 and everything the hooks' requirements.txt lists, like
# save-plan.sh - the item count is parsed out of each manifest rather than
# matched line by line.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/resolve-personal-notes-config.sh"

if [ $# -gt 0 ]; then
  echo "Unexpected argument: $1" >&2
  echo "Usage: ${BASH_SOURCE[0]}" >&2
  exit 1
fi

if ! command -v python3 > /dev/null 2>&1; then
  echo "python3 is required to parse plan manifests and render the report." >&2
  exit 1
fi
# Every requirement is reported, and none is named here: the hooks'
# requirements file is where a dependency is written down, so adding one there
# is enough for this check to start covering it.
MISSING_REQUIREMENTS="$(python3 -m "${MISSING_REQUIREMENTS_MODULE}" \
  "${PROJECT_ROOT}/${HOOKS_REQUIREMENTS_FILE}")"
if [ -n "${MISSING_REQUIREMENTS}" ]; then
  echo "Not installed: ${MISSING_REQUIREMENTS}" >&2
  echo "Run: pip install -r ${HOOKS_REQUIREMENTS_FILE}" >&2
  exit 1
fi

if ! fetch_personal_notes_branch; then
  echo "Branch '${NOTES_BRANCH}' doesn't exist yet (tried: ${ATTEMPTED_NOTES_REMOTES})." >&2
  echo "Run ${CREATE_PERSONAL_NOTES_BRANCH_SCRIPT} first, then re-run this script." >&2
  exit 1
fi

SCRATCH_DIR="$(mktemp -d)"
cleanup() {
  rm -rf "${SCRATCH_DIR}"
}
trap cleanup EXIT

# Only the two files the budget is spent on are materialized: everything else
# under PLANS_DIR is generated data (the branch index, the dashboard-URL
# cache), which no plan is charged for.
while IFS= read -r file_path; do
  case "$(basename "${file_path}")" in
    "${PLAN_MANIFEST_FILENAME}" | "${PLAN_ROADMAP_FILENAME}") ;;
    *) continue ;;
  esac
  destination="${SCRATCH_DIR}/${file_path#"${PLANS_DIR}"/}"
  mkdir -p "$(dirname "${destination}")"
  git show "FETCH_HEAD:${file_path}" > "${destination}"
done < <(git ls-tree -r --name-only FETCH_HEAD -- "${PLANS_DIR}")

echo "=== Plan sizes on '${NOTES_BRANCH}' (remote '${ACTIVE_NOTES_REMOTE}') ==="
python3 -m "${PLAN_SIZE_BUDGET_MODULE}" \
  --plans-dir "${SCRATCH_DIR}" \
  --manifest-filename "${PLAN_MANIFEST_FILENAME}" \
  --roadmap-filename "${PLAN_ROADMAP_FILENAME}"
