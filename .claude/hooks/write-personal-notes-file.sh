#!/bin/bash
set -euo pipefail

# "Commit and push one file to the personal-notes branch" - the personal-notes
# shaped caller of ./write-branch-files.sh. Every write in this system that
# isn't already served by a purpose-built script (save-personal-notes.sh for
# CLAUDE.local.md, save-plan.sh for a plan's manifest/roadmap/branch-index
# trio) is exactly this shape: copy one already-prepared local file to one
# destination path, commit, push, done.
#
# Usage:
#   "$CLAUDE_PROJECT_DIR/.claude/hooks/write-personal-notes-file.sh" \
#     --source <local-file> \
#     --destination <repo-relative-path> \
#     --message <commit-message>
#
# Resolves the remote/branch exactly like every other hook script here (git
# config > environment variable > the zero-config default, plus the
# same-branch-upstream fallback - see fetch_personal_notes_branch in
# ./resolve-personal-notes-config.sh). What it adds over the primitive is that
# resolution, and the one rule that comes with it: the notes branch is never
# created here. A missing branch means the one-time setup hasn't been done, and
# ./create-personal-notes-branch.sh is what does it, with all its safeguards
# against creating a second, divergent copy.
#
# Safe to re-run: a no-op (exit 0, nothing pushed) if --destination's content
# on the branch already matches --source. Does its work in a scratch worktree,
# so it never touches the caller's current branch or working tree.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/resolve-personal-notes-config.sh"

SOURCE_FILE=""
DESTINATION_PATH=""
COMMIT_MESSAGE=""
while [ $# -gt 0 ]; do
  case "$1" in
    --source)
      SOURCE_FILE="$2"
      shift 2
      ;;
    --destination)
      DESTINATION_PATH="$2"
      shift 2
      ;;
    --message)
      COMMIT_MESSAGE="$2"
      shift 2
      ;;
    *)
      echo "Unrecognized argument: $1" >&2
      exit 1
      ;;
  esac
done

if [ -z "${SOURCE_FILE}" ] || [ -z "${DESTINATION_PATH}" ] || [ -z "${COMMIT_MESSAGE}" ]; then
  echo "Usage: ${BASH_SOURCE[0]} --source <local-file> --destination <repo-relative-path> --message <commit-message>" >&2
  exit 1
fi

if ! fetch_personal_notes_branch; then
  echo "Branch '${NOTES_BRANCH}' doesn't exist yet (tried: ${ATTEMPTED_NOTES_REMOTES})." >&2
  echo "Run ./create-personal-notes-branch.sh first, then re-run this script." >&2
  exit 1
fi

# Pushed back to whichever remote actually served the branch, not
# unconditionally to NOTES_REMOTE, so a save always lands where the notes came
# from. --create-branch-if-absent is deliberately not passed: the guard above
# has already established that the branch exists, and creating one here would
# bypass create-personal-notes-branch.sh's safeguards.
exec bash "${WRITE_BRANCH_FILES_SCRIPT}" \
  --remote "${ACTIVE_NOTES_REMOTE}" \
  --branch "${NOTES_BRANCH}" \
  --message "${COMMIT_MESSAGE}" \
  --file "${SOURCE_FILE}:${DESTINATION_PATH}"
