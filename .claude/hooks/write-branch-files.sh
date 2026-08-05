#!/bin/bash
set -euo pipefail

# Generic "commit these files to this branch on this remote" primitive: the
# worktree dance every write in this system performs, with the branch and the
# file set as arguments rather than fixed.
#
# Usage:
#   "$CLAUDE_PROJECT_DIR/.claude/hooks/write-branch-files.sh" \
#     --remote <name-or-url> \
#     --branch <branch> \
#     --message <commit-message> \
#     --file <source>:<destination> [--file <source>:<destination> ...] \
#     [--create-branch-if-absent]
#
# ./write-personal-notes-file.sh is the personal-notes-shaped caller of this,
# and ./setup-stacked-prs.sh the fork-overlay one - a tooling branch is the
# same operation with several files and a branch nobody has created yet, which
# is what --create-branch-if-absent covers. Without that flag a missing branch
# is an error, so a caller that expects the branch to exist never silently
# creates a second, divergent one.
#
# Safe to re-run: a no-op (exit 0, nothing pushed) when every destination's
# content on the branch already matches its source. Does its work in a scratch
# worktree, so it never touches the caller's current branch or working tree.
# Every file lands in one commit.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/resolve-personal-notes-config.sh"

usage() {
  echo "Usage: ${BASH_SOURCE[0]} --remote <name-or-url> --branch <branch>" >&2
  echo "         --message <commit-message> --file <source>:<destination> ..." >&2
  echo "         [--create-branch-if-absent]" >&2
}

# %% arguments

REMOTE=""
BRANCH=""
COMMIT_MESSAGE=""
CREATE_BRANCH_IF_ABSENT=0
SOURCE_FILES=()
DESTINATION_PATHS=()

# add_file: validates one --file argument and records its two halves.
# Split on the last colon, so a source path containing one is still read
# correctly - the destination is repo-relative and can never contain one.
add_file() {
  local pair="$1" source_file destination_path
  case "${pair}" in
    *:*) ;;
    *)
      echo "--file takes <source>:<destination>, not: ${pair}" >&2
      exit 1
      ;;
  esac
  source_file="${pair%:*}"
  destination_path="${pair##*:}"

  if [ ! -f "${source_file}" ]; then
    echo "--file source not found: ${source_file}" >&2
    exit 1
  fi
  case "${destination_path}" in
    /* | */../* | ../* | */.. | .. | "")
      echo "--file destination must be a relative path with no '..' component and" >&2
      echo "no leading '/': ${destination_path}" >&2
      exit 1
      ;;
  esac

  SOURCE_FILES+=("${source_file}")
  DESTINATION_PATHS+=("${destination_path}")
}

while [ $# -gt 0 ]; do
  case "$1" in
    --remote)
      REMOTE="${2:-}"
      shift 2
      ;;
    --branch)
      BRANCH="${2:-}"
      shift 2
      ;;
    --message)
      COMMIT_MESSAGE="${2:-}"
      shift 2
      ;;
    --file)
      add_file "${2:-}"
      shift 2
      ;;
    --create-branch-if-absent)
      CREATE_BRANCH_IF_ABSENT=1
      shift
      ;;
    *)
      echo "Unrecognized argument: $1" >&2
      usage
      exit 1
      ;;
  esac
done

for required in "--remote:${REMOTE}" "--branch:${BRANCH}" "--message:${COMMIT_MESSAGE}"; do
  if [ -z "${required#*:}" ]; then
    echo "${required%%:*} is required." >&2
    usage
    exit 1
  fi
done
if [ ${#SOURCE_FILES[@]} -eq 0 ]; then
  echo "--file is required at least once." >&2
  usage
  exit 1
fi

# %% the branch to write to

BRANCH_EXISTS=1
git fetch "${REMOTE}" "${BRANCH}" --quiet 2> /dev/null || BRANCH_EXISTS=0

if [ "${BRANCH_EXISTS}" = "0" ] && [ "${CREATE_BRANCH_IF_ABSENT}" != "1" ]; then
  echo "Branch '${BRANCH}' doesn't exist on '${REMOTE}'." >&2
  echo "Pass --create-branch-if-absent to have it created." >&2
  exit 1
fi

SCRATCH_DIR="$(mktemp -d)"
# Suffixed with $$ (this process's PID) so two concurrent invocations never
# race over the same worktree branch name.
SCRATCH_BRANCH="__write-branch-files-tmp-$$"
cleanup() {
  git worktree remove --force "${SCRATCH_DIR}" 2> /dev/null || rm -rf "${SCRATCH_DIR}"
  git branch -D "${SCRATCH_BRANCH}" > /dev/null 2>&1 || true
}
trap cleanup EXIT

git branch -D "${SCRATCH_BRANCH}" > /dev/null 2>&1 || true
if [ "${BRANCH_EXISTS}" = "1" ]; then
  # FETCH_HEAD, not "<remote>/<branch>": a URL-form remote creates no
  # remote-tracking ref, but FETCH_HEAD always points at what was just fetched.
  git worktree add -b "${SCRATCH_BRANCH}" "${SCRATCH_DIR}" FETCH_HEAD --quiet
else
  # An orphan, so a branch created here carries only these files rather than
  # the history of whatever the caller happened to have checked out.
  git worktree add --orphan -b "${SCRATCH_BRANCH}" "${SCRATCH_DIR}" --quiet
  git -C "${SCRATCH_DIR}" rm -rf --quiet . > /dev/null 2>&1 || true
fi

# %% the files

for index in "${!SOURCE_FILES[@]}"; do
  destination_path="${DESTINATION_PATHS[${index}]}"
  mkdir -p "${SCRATCH_DIR}/$(dirname "${destination_path}")"
  cp "${SOURCE_FILES[${index}]}" "${SCRATCH_DIR}/${destination_path}"
  git -C "${SCRATCH_DIR}" add "${destination_path}"
done

if git -C "${SCRATCH_DIR}" diff --cached --quiet; then
  echo "No changes - '${BRANCH}' on '${REMOTE}' already matches every file given."
  exit 0
fi

git -C "${SCRATCH_DIR}" commit --quiet -m "${COMMIT_MESSAGE}"
git -C "${SCRATCH_DIR}" push --quiet "${REMOTE}" "HEAD:${BRANCH}"

echo "Wrote ${#SOURCE_FILES[@]} file(s) to '${BRANCH}' on '${REMOTE}'."
