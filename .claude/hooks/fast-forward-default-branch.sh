#!/bin/bash
set -euo pipefail

# Keeps the base every session starts from level with the upstream repository
# this fork tracks.
#
# The defect this exists for: sessions are cut from the fork's default branch.
# When that branch has drifted behind the upstream it is forked from, every
# session in that clone plans, reviews and implements against a base that is
# already stale - and nothing in the session says so, because the clone itself
# is perfectly consistent. Discipline does not fix it: noticing is the step
# that gets skipped, and by the time a rebase surfaces the drift the work is
# already written against the old base.
#
# What it does, in one pass:
#   1. resolves the upstream repository and the branch it is tracked from;
#   2. fetches that branch;
#   3. fast-forwards this clone's copy of it;
#   4. pushes the result to the fork, whose default branch is what the *next*
#      session gets cloned from.
#
# Fast-forward only, in every step. Nothing here rebases, merges non-trivially,
# or force-pushes: a default branch that has commits the upstream does not is
# reported and left exactly as it is. It is never a conflict in normal use,
# because the fork's default branch is only ever written to by this catching-up
# and never committed to directly.
#
# Only the default branch is touched. The checked-out branch is never merged or
# rebased - whether to take a moved base into work already in progress is the
# session's call, not a hook's - but how far behind it now is gets reported, so
# the choice is made rather than missed.
#
# Where the upstream comes from: `<STACK_SCRIPT> configuration`, the same
# resolution the stacked-PR tooling runs on (see ../stack/stack.toml for the
# committed defaults and the personal-notes override it layers on top). No
# repository is named here, so this works unchanged on any fork of any
# repository - and there is only one place to correct if the upstream ever
# moves.
#
# Never fatal. Every refusal - no configuration, unresolvable remotes, an
# unreachable upstream, a diverged or pinned-down base, a rejected push -
# reports what happened and exits 0, because a session that cannot sync its
# base must still start.
#
# Output: the outcome on the first line, then zero or more indented rows naming
# what is left for the session to do. ./session-start.sh prints the block
# verbatim as its "default branch" summary line. Also runnable by hand, to
# catch a long-running session's clone up mid-session.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/resolve-personal-notes-config.sh"
source "${SCRIPT_DIR}/session-start-messages.sh"

FOLLOW_UP_ROW_INDENT="    "

# report: prints the outcome and its rows in the shape session-start.sh embeds.
report() {
  local outcome="$1"
  shift
  printf '%s\n' "${outcome}"
  local row
  for row in "$@"; do
    printf '%s%s\n' "${FOLLOW_UP_ROW_INDENT}" "${row}"
  done
}

# configuration_value: reads one setting out of the resolved stacked-PR
# configuration, which prints one `field<TAB>value` line per setting.
configuration_value() {
  printf '%s\n' "${CONFIGURATION}" | awk -F'\t' -v field="$1" '$1 == field { print $2; exit }'
}

if [ ! -f "${PROJECT_ROOT}/${STACK_CONFIG_FILE}" ]; then
  report "$(default_branch_line_not_configured "${STACK_CONFIG_FILE}")"
  exit 0
fi

# The refusal itself is the report: `configuration` already words exactly which
# remote it could not resolve and how to say which one it is, and rewording that
# here would be a second, vaguer copy of it.
RESOLUTION_REFUSAL="$(mktemp)"
trap 'rm -f "${RESOLUTION_REFUSAL}"' EXIT
if ! CONFIGURATION="$(python3 "${PROJECT_ROOT}/${STACK_SCRIPT}" configuration \
    2>"${RESOLUTION_REFUSAL}")"; then
  report "$(default_branch_line_upstream_unresolved "$(cat "${RESOLUTION_REFUSAL}")")"
  exit 0
fi

UPSTREAM_REPOSITORY="$(configuration_value upstream_repository)"
UPSTREAM_REMOTE="$(configuration_value upstream_remote)"
BASE_BRANCH="$(configuration_value upstream_base)"
FORK_REMOTE="$(configuration_value fork_remote)"

# A clone that has already added the upstream remote is fetched by its name; one
# that has not is fetched by URL, which git accepts just as readily and which
# saves a session having to add a remote it will not otherwise use.
if git remote get-url "${UPSTREAM_REMOTE}" >/dev/null 2>&1; then
  UPSTREAM_LOCATION="${UPSTREAM_REMOTE}"
else
  UPSTREAM_LOCATION="https://github.com/${UPSTREAM_REPOSITORY}.git"
fi

if ! git fetch --quiet "${UPSTREAM_LOCATION}" "${BASE_BRANCH}" 2>/dev/null; then
  report "$(default_branch_line_upstream_unreachable \
    "${BASE_BRANCH}" "${UPSTREAM_REPOSITORY}")"
  exit 0
fi
UPSTREAM_TIP="$(git rev-parse FETCH_HEAD)"

# Empty on a clone checked out with no local copy of the base branch at all, in
# which case there is nothing to be behind and the fetch below creates it.
LOCAL_TIP="$(git rev-parse --verify --quiet "refs/heads/${BASE_BRANCH}" || true)"

if [ -n "${LOCAL_TIP}" ] && [ "${LOCAL_TIP}" != "${UPSTREAM_TIP}" ] \
    && ! git merge-base --is-ancestor "${LOCAL_TIP}" "${UPSTREAM_TIP}"; then
  report "$(default_branch_line_diverged "${BASE_BRANCH}" "${UPSTREAM_REPOSITORY}")"
  exit 0
fi

COMMITS_BEHIND=0
if [ -n "${LOCAL_TIP}" ]; then
  COMMITS_BEHIND="$(git rev-list --count "${LOCAL_TIP}..${UPSTREAM_TIP}")"
fi

# Two ways to move the same ref, because git refuses to fetch into the branch
# that is checked out: a merge when the base is what the session is sitting on,
# a fetch into the ref otherwise, which needs no working-tree change at all.
# Both are fast-forward only.
if [ "${LOCAL_TIP}" != "${UPSTREAM_TIP}" ]; then
  if [ "$(git rev-parse --abbrev-ref HEAD)" = "${BASE_BRANCH}" ]; then
    if ! git merge --ff-only --quiet FETCH_HEAD 2>/dev/null; then
      report "$(default_branch_line_local_update_refused \
        "${BASE_BRANCH}" "${UPSTREAM_REPOSITORY}")"
      exit 0
    fi
  else
    git fetch --quiet "${UPSTREAM_LOCATION}" "${BASE_BRANCH}:${BASE_BRANCH}"
  fi
fi

# The fork is caught up on its own evidence rather than on the local branch
# having moved: a clone whose base was already current still leaves every later
# clone stale if an earlier session's push was refused and nobody noticed.
FORK_TIP="$(git rev-parse --verify --quiet \
  "refs/remotes/${FORK_REMOTE}/${BASE_BRANCH}" || true)"
FOLLOW_UP_ROWS=()
if [ "${FORK_TIP}" != "${UPSTREAM_TIP}" ]; then
  if git push --quiet "${FORK_REMOTE}" "${BASE_BRANCH}" 2>/dev/null; then
    FOLLOW_UP_ROWS+=("$(default_branch_row_fork_pushed "${FORK_REMOTE}")")
  else
    FOLLOW_UP_ROWS+=("$(default_branch_row_fork_push_failed "${FORK_REMOTE}")")
  fi
fi

CURRENT_BRANCH_BEHIND="$(git rev-list --count "HEAD..refs/heads/${BASE_BRANCH}")"
if [ "${CURRENT_BRANCH_BEHIND}" != "0" ]; then
  FOLLOW_UP_ROWS+=("$(default_branch_row_current_branch_behind \
    "${BASE_BRANCH}" "${CURRENT_BRANCH_BEHIND}")")
fi

if [ "${COMMITS_BEHIND}" = "0" ]; then
  OUTCOME="$(default_branch_line_current "${BASE_BRANCH}" "${UPSTREAM_REPOSITORY}")"
else
  OUTCOME="$(default_branch_line_fast_forwarded \
    "${BASE_BRANCH}" "${COMMITS_BEHIND}" "${UPSTREAM_REPOSITORY}")"
fi
report "${OUTCOME}" ${FOLLOW_UP_ROWS+"${FOLLOW_UP_ROWS[@]}"}
