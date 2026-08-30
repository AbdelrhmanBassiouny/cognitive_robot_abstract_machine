#!/bin/bash
set -euo pipefail

# Publishes a built site directory as the whole content of a branch, which is what
# GitHub Pages then serves.
#
# The branch carries the site and nothing else, so each publish replaces it entirely
# rather than merging into it - a plan deleted from the notes branch has to stop being
# served, and a page left behind by an earlier build would go on being served forever.
# Each publish is one commit on top of the last, so the branch keeps the site's history.
#
# Usage:
#   publish_site.sh --source <built site directory> --branch <branch> \
#     --remote <remote> --message <commit message>
#
# Safe to re-run: a no-op (exit 0, nothing pushed) when the branch already carries
# exactly this content, so an unchanged rebuild adds no empty commit. Does its work in
# a scratch worktree, so it never touches the caller's current branch or working tree.

SOURCE_DIRECTORY=""
BRANCH=""
REMOTE=""
COMMIT_MESSAGE=""
while [ $# -gt 0 ]; do
  case "$1" in
    --source)
      SOURCE_DIRECTORY="$2"
      shift 2
      ;;
    --branch)
      BRANCH="$2"
      shift 2
      ;;
    --remote)
      REMOTE="$2"
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

if [ -z "${SOURCE_DIRECTORY}" ] || [ -z "${BRANCH}" ] || [ -z "${REMOTE}" ] \
    || [ -z "${COMMIT_MESSAGE}" ]; then
  echo "Usage: ${BASH_SOURCE[0]} --source <directory> --branch <branch> --remote <remote> --message <message>" >&2
  exit 1
fi
if [ ! -d "${SOURCE_DIRECTORY}" ]; then
  echo "--source directory not found: ${SOURCE_DIRECTORY}" >&2
  exit 1
fi

SCRATCH_DIRECTORY="$(mktemp -d)"
# Suffixed with this process's PID, so two concurrent publishes never race over the
# same worktree branch name.
SCRATCH_BRANCH="__publish-site-tmp-$$"
cleanup() {
  git worktree remove --force "${SCRATCH_DIRECTORY}" 2>/dev/null || rm -rf "${SCRATCH_DIRECTORY}"
  git branch -D "${SCRATCH_BRANCH}" > /dev/null 2>&1 || true
}
trap cleanup EXIT

git branch -D "${SCRATCH_BRANCH}" > /dev/null 2>&1 || true

# FETCH_HEAD, not "${REMOTE}/${BRANCH}": a URL-form remote creates no remote-tracking
# ref, but FETCH_HEAD always names what was just fetched. A branch that does not exist
# yet is the first publish, which starts the history rather than continuing one.
if git fetch "${REMOTE}" "${BRANCH}" --quiet 2>/dev/null; then
  git worktree add -b "${SCRATCH_BRANCH}" "${SCRATCH_DIRECTORY}" FETCH_HEAD --quiet
  git -C "${SCRATCH_DIRECTORY}" rm -r --quiet --ignore-unmatch .
else
  git worktree add --detach "${SCRATCH_DIRECTORY}" --quiet
  git -C "${SCRATCH_DIRECTORY}" checkout --orphan "${SCRATCH_BRANCH}" --quiet
  git -C "${SCRATCH_DIRECTORY}" rm -rf --quiet --ignore-unmatch .
fi

cp -R "${SOURCE_DIRECTORY}/." "${SCRATCH_DIRECTORY}/"
# Pages runs a Jekyll build over the branch unless told not to, which drops every path
# beginning with an underscore and rewrites the rest. The site is already HTML.
touch "${SCRATCH_DIRECTORY}/.nojekyll"
git -C "${SCRATCH_DIRECTORY}" add --all

if git -C "${SCRATCH_DIRECTORY}" diff --cached --quiet; then
  echo "The site on '${BRANCH}' is already up to date - nothing published."
  exit 0
fi

git -C "${SCRATCH_DIRECTORY}" commit --quiet -m "${COMMIT_MESSAGE}"
git -C "${SCRATCH_DIRECTORY}" push --quiet "${REMOTE}" "HEAD:${BRANCH}"

echo "Published the site to '${BRANCH}' on '${REMOTE}'."
