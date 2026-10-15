#!/bin/bash
set -euo pipefail

# Persists a plan's edited manifest and roadmap onto the personal-notes
# branch, at
# .claude/personal/plans/<plan-id>/{plan.yaml,roadmap.md} - and regenerates
# the generated branch->plan-id reverse index
# (.claude/personal/plans/_generated/branch-index.tsv) in the same commit,
# scanning every plan's plan.yaml so it can never drift out of sync with
# the manifests it's derived from. See
# .claude/skills/plan-dashboard/plan-schema.md for the
# full plan.yaml schema, and .claude/skills/plan-dashboard/SKILL.md for how
# the manifest is consumed.
#
# Usage, after copying the plan's files off the personal-notes branch and
# editing them:
#   "$CLAUDE_PROJECT_DIR/.claude/hooks/save-plan.sh" <plan-id> \
#     --manifest <path/to/plan.yaml> --roadmap <path/to/roadmap.md>
# The plan id is always explicit with these flags, since a brand-new plan has
# no entry in the reverse index yet to derive it from.
#
# Without the flags, the manifest and roadmap are read from CLAUDE.local.md
# between BEGIN-PLAN-MANIFEST/END-PLAN-MANIFEST and
# BEGIN-PLAN-ROADMAP/END-PLAN-ROADMAP markers a session wrote there itself
# (session-start.sh loads only the branch's own item, read-only, and writes
# no such markers), and <plan-id> may be omitted when the current branch is
# one of the plan's items.
#
# Before anything is pushed, landed items are dropped (with every depends_on
# edge to them), a plan left with no items is removed, and a plan over the
# limits in basstler/src/basstler/plan_size_limits.py is refused, naming
# each violation.
#
# This script pushes data only. It never calls the Artifact tool (only a
# live Claude session can), so it does not regenerate the dashboard itself -
# it prints a reminder to run /plan-dashboard <plan-id> afterward.
#
# Requires the package's interpreter with its dependencies to parse, prune and
# check manifests and to regenerate the reverse index (a session start sets that
# interpreter up).
#
# Resolves the remote/branch exactly like the other hook scripts (git
# config > environment variable > the zero-config default, plus the
# same-branch-upstream fallback - see fetch_personal_notes_branch in
# ./resolve-personal-notes-config.sh).
#
# Safe to re-run: a no-op if the extracted content already matches what's on
# the branch (checked across all three files it may touch). Does its work in
# a scratch worktree, so it never touches your current branch or working
# tree - and never touches the plan's own branch(es), or anything that could
# be merged: the manifest lives only on the personal-notes branch. Fails
# with a clear message if that branch doesn't exist yet on any resolved
# remote - run ./create-personal-notes-branch.sh first in that case.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/resolve-personal-notes-config.sh"

require_basstler_python

PLAN_ID=""
MANIFEST_SOURCE_FILE=""
ROADMAP_SOURCE_FILE=""
while [ $# -gt 0 ]; do
  case "$1" in
    --manifest)
      MANIFEST_SOURCE_FILE="$2"
      shift 2
      ;;
    --roadmap)
      ROADMAP_SOURCE_FILE="$2"
      shift 2
      ;;
    -*)
      echo "Unrecognized argument: $1" >&2
      exit 1
      ;;
    *)
      PLAN_ID="$1"
      shift
      ;;
  esac
done

if [ -n "${MANIFEST_SOURCE_FILE}" ] && [ -z "${ROADMAP_SOURCE_FILE}" ]; then
  echo "--manifest was given without --roadmap - they must be passed together." >&2
  exit 1
fi
if [ -z "${MANIFEST_SOURCE_FILE}" ] && [ -n "${ROADMAP_SOURCE_FILE}" ]; then
  echo "--roadmap was given without --manifest - they must be passed together." >&2
  exit 1
fi
BOOTSTRAP_FROM_FILES=0
if [ -n "${MANIFEST_SOURCE_FILE}" ]; then
  BOOTSTRAP_FROM_FILES=1
  if [ -z "${PLAN_ID}" ]; then
    echo "<plan-id> is required alongside --manifest/--roadmap - a brand-new" >&2
    echo "plan has no entry in the reverse index yet to auto-derive it from." >&2
    exit 1
  fi
fi

if [ "${BOOTSTRAP_FROM_FILES}" = "0" ]; then
  if [ ! -f "${CLAUDE_LOCAL_MD}" ]; then
    echo "No CLAUDE.local.md at the project root (${CLAUDE_LOCAL_MD}) - nothing to save." >&2
    exit 1
  fi
  if ! grep -q '^<!-- BEGIN-PLAN-MANIFEST:' "${CLAUDE_LOCAL_MD}" \
      || ! grep -q '^<!-- BEGIN-PLAN-ROADMAP:' "${CLAUDE_LOCAL_MD}"; then
    echo "CLAUDE.local.md has no plan-manifest/plan-roadmap section to extract." >&2
    echo "Run session-start.sh first (on a branch a plan already tracks), pass" >&2
    echo "--manifest/--roadmap file paths instead, or add the marker pairs" >&2
    echo "yourself when bootstrapping a brand-new plan - see the header" >&2
    echo "comment in this script." >&2
    exit 1
  fi
fi

if ! fetch_personal_notes_branch; then
  echo "Branch '${NOTES_BRANCH}' doesn't exist yet (tried: ${ATTEMPTED_NOTES_REMOTES})." >&2
  echo "Run ./create-personal-notes-branch.sh first, then re-run this script." >&2
  exit 1
fi

if [ -z "${PLAN_ID}" ]; then
  PLAN_ID="$(plan_id_for_branch "$(git rev-parse --abbrev-ref HEAD)" || true)"
fi
if [ -z "${PLAN_ID}" ]; then
  echo "Could not determine which plan to save for - the current branch isn't in" >&2
  echo "the generated index yet. Pass the plan id explicitly:" >&2
  echo "  ${BASH_SOURCE[0]} <plan-id>" >&2
  exit 1
fi
if ! printf '%s' "${PLAN_ID}" | grep -qE '^[A-Za-z0-9][A-Za-z0-9_-]*$'; then
  echo "Invalid plan id '${PLAN_ID}' - must match ^[A-Za-z0-9][A-Za-z0-9_-]*\$" >&2
  echo "(no path separators, no '..', no leading dot/dash) - it is used directly" >&2
  echo "as a path component." >&2
  exit 1
fi

MANIFEST_FILE="$(mktemp)"
ROADMAP_FILE="$(mktemp)"
SCRATCH_DIR="$(mktemp -d)"
# Suffixed with $$ (this process's PID) so two concurrent invocations never
# race over the same worktree branch name.
SCRATCH_BRANCH="__save-plan-tmp-$$"
cleanup() {
  git worktree remove --force "${SCRATCH_DIR}" 2>/dev/null || rm -rf "${SCRATCH_DIR}"
  git branch -D "${SCRATCH_BRANCH}" > /dev/null 2>&1 || true
  rm -f "${MANIFEST_FILE}" "${ROADMAP_FILE}"
}
trap cleanup EXIT

# BOOTSTRAP_FROM_FILES was set above from whether --manifest/--roadmap were
# passed (see the argument-parsing block): "1" reads the manifest/roadmap
# straight from the given files, "0" extracts them from CLAUDE.local.md's
# markers instead - see this script's own header comment for when each
# path applies.
if [ "${BOOTSTRAP_FROM_FILES}" = "1" ]; then
  cp "${MANIFEST_SOURCE_FILE}" "${MANIFEST_FILE}"
  cp "${ROADMAP_SOURCE_FILE}" "${ROADMAP_FILE}"
else
  awk '/^<!-- BEGIN-PLAN-MANIFEST:/{flag=1; next} /^<!-- END-PLAN-MANIFEST -->$/{flag=0} flag' \
    "${CLAUDE_LOCAL_MD}" > "${MANIFEST_FILE}"
  awk '/^<!-- BEGIN-PLAN-ROADMAP:/{flag=1; next} /^<!-- END-PLAN-ROADMAP -->$/{flag=0} flag' \
    "${CLAUDE_LOCAL_MD}" > "${ROADMAP_FILE}"
fi

if [ ! -s "${MANIFEST_FILE}" ]; then
  echo "The plan manifest is empty - nothing to save." >&2
  exit 1
fi

MANIFEST_PLAN_ID="$("${BASSTLER_PYTHON}" -m "${PLAN_MANIFEST_TOOLS_MODULE}" read-id "${MANIFEST_FILE}")"
if [ "${MANIFEST_PLAN_ID}" != "${PLAN_ID}" ]; then
  echo "The plan manifest's 'id: ${MANIFEST_PLAN_ID}' does not match the plan" >&2
  echo "being saved ('${PLAN_ID}') - refusing to save under a mismatched key." >&2
  exit 1
fi

git branch -D "${SCRATCH_BRANCH}" > /dev/null 2>&1 || true
git worktree add -b "${SCRATCH_BRANCH}" "${SCRATCH_DIR}" FETCH_HEAD --quiet

PLAN_DIRECTORY_PATH="$(plan_directory_path "${PLAN_ID}")"
MANIFEST_PATH="$(plan_manifest_path "${PLAN_ID}")"
ROADMAP_PATH="$(plan_roadmap_path "${PLAN_ID}")"
# Prints "saved", or "removed" once every item has landed; exits 1 naming each
# limit a plan breaks.
STAGED_PLAN="$("${BASSTLER_PYTHON}" -m "${PLAN_SIZE_LIMITS_MODULE}" stage \
  "${MANIFEST_FILE}" "${ROADMAP_FILE}" \
  --manifest-destination "${SCRATCH_DIR}/${MANIFEST_PATH}" \
  --roadmap-destination "${SCRATCH_DIR}/${ROADMAP_PATH}")" || exit 1

mkdir -p "$(dirname "${SCRATCH_DIR}/${PLAN_BRANCH_INDEX_PATH}")"
"${BASSTLER_PYTHON}" -m "${PLAN_MANIFEST_TOOLS_MODULE}" regenerate-branch-index \
  --scratch-dir "${SCRATCH_DIR}" \
  --plans-dir "${PLANS_DIR}" \
  --manifest-filename "${PLAN_MANIFEST_FILENAME}" \
  --output "${SCRATCH_DIR}/${PLAN_BRANCH_INDEX_PATH}"

git -C "${SCRATCH_DIR}" add --all -- \
  "${PLAN_DIRECTORY_PATH}" \
  "${PLAN_BRANCH_INDEX_PATH}"

if git -C "${SCRATCH_DIR}" diff --cached --quiet; then
  echo "No changes to save - plan '${PLAN_ID}' on '${NOTES_BRANCH}' (remote '${ACTIVE_NOTES_REMOTE}') is already up to date."
  exit 0
fi

git -C "${SCRATCH_DIR}" commit --quiet -m "Update plan manifest for ${PLAN_ID}"
git -C "${SCRATCH_DIR}" push "${ACTIVE_NOTES_REMOTE}" "HEAD:${NOTES_BRANCH}"

if [ "${STAGED_PLAN}" = "removed" ]; then
  echo "Every item of plan '${PLAN_ID}' has landed, so the plan was removed from '${NOTES_BRANCH}' on '${ACTIVE_NOTES_REMOTE}'."
  exit 0
fi
echo "Saved plan '${PLAN_ID}' (plan.yaml, roadmap.md, and the branch index) back to '${NOTES_BRANCH}' on '${ACTIVE_NOTES_REMOTE}'."
echo "Run /plan-dashboard ${PLAN_ID} to refresh its dashboard Artifact - this script only pushes data, it can't call the Artifact tool itself."
