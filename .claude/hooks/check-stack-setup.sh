#!/bin/bash
set -euo pipefail

# Reports whether this clone has everything the stacked-PR workflow needs - the
# tooling files, the fork and upstream remotes its configuration names, and a
# board that can never be committed - so a session (or a person) can tell in one
# call what is already set up and what still needs doing.
#
# Usage (from anywhere - always inspects this repo specifically, see
# resolve-personal-notes-config.sh):
#   ./.claude/hooks/check-stack-setup.sh
#
# The stack-side counterpart of ./check-setup.sh, with the same output contract:
# one tab-separated "<check>\t<status>\t<detail>" row per check, statuses
# ok / needs-setup / info, and exit 0 only when no row is needs-setup. See that
# script's header for why the format is TSV.
#
# Read-only: it fetches (into FETCH_HEAD), lists remote refs and reads git
# config, but never writes config, branches, files or remotes.
#
# The rows are ordered so an earlier one can be a prerequisite of a later one,
# with one departure from check-setup.sh's shape: the "does it all work
# together?" check (`stack_configuration`) comes third rather than last,
# because the remote checks below it can only run once the configuration says
# which remotes to look for. When it fails, those rows report "not checked"
# instead of guessing at default names.
#
# Labels and the Routine are deliberately out of scope. Both are real parts of
# the setup, but neither is answerable from a clone: labels live behind the
# GitHub API (./setup-stacked-prs.sh checks them through ./github-api.sh) and
# the Routine lives in claude.ai/code/routines, which nothing here can read.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/resolve-personal-notes-config.sh"

EXIT_CODE=0

# report: prints one TSV row, and remembers that the overall run failed if the
# status is needs-setup, so the exit code never has to be tracked by hand at
# each call site.
report() {
  local check="$1" status="$2" detail="$3"
  [ "${status}" != "needs-setup" ] || EXIT_CODE=1
  printf '%s\t%s\t%s\n' "${check}" "${status}" "${detail}"
}

# %% the tooling itself

MISSING_TOOLING=""
for tooling_path in \
    "${STACK_SCRIPT}" \
    "${STACK_CONFIG_FILE}" \
    "${STACK_README_FILE}" \
    "${STACK_ROUTINE_DOCUMENT}" \
    "${STACK_ROUTINE_PROMPT_FILE}"; do
  [ -f "${tooling_path}" ] || MISSING_TOOLING="${MISSING_TOOLING} ${tooling_path}"
done
if [ -n "${MISSING_TOOLING}" ]; then
  report stack_tooling_files needs-setup \
    "this checkout is missing:${MISSING_TOOLING} - merge the stack tooling into your fork's default branch, or install it with /setup-stacked-prs --mode fork-overlay"
else
  report stack_tooling_files ok "stack.py, stack.toml, README.md, ROUTINE.md and routine-prompt.md are all present"
fi

# tomllib, which stack.py imports to read its own configuration, is standard
# library only from 3.11 - so an older interpreter fails at import rather than
# at any behaviour a later check would notice.
PYTHON_TOML_SUPPORT=0
if command -v python3 > /dev/null 2>&1 && python3 -c 'import tomllib' 2> /dev/null; then
  PYTHON_TOML_SUPPORT=1
  report python_toml_support ok "python3 $(python3 -c 'import sys; print(".".join(map(str, sys.version_info[:2])))') provides tomllib"
else
  report python_toml_support needs-setup \
    "python3 with tomllib (3.11 or newer) is not available, so stack.py cannot read its configuration at all"
fi

# %% the configuration everything below is measured against

# Asked of stack.py rather than parsed out of stack.toml here: the personal
# .claude/personal/stack.toml override wins over the committed defaults, and
# load_config is the single place that knows it. Reading the file directly
# would check the wrong remotes for exactly the contributor this setup exists
# for.
STACK_CONFIGURATION=""
CONFIGURATION_RESOLVED=0
if [ -z "${MISSING_TOOLING}" ] && [ "${PYTHON_TOML_SUPPORT}" = "1" ] \
    && STACK_CONFIGURATION="$(python3 "${STACK_SCRIPT}" config 2> /dev/null)"; then
  CONFIGURATION_RESOLVED=1
fi

# configured_value: prints one setting from the resolved configuration.
configured_value() {
  printf '%s\n' "${STACK_CONFIGURATION}" | awk -F'\t' -v name="$1" '$1 == name { print $2; exit }'
}

if [ "${CONFIGURATION_RESOLVED}" = "1" ]; then
  FORK_REMOTE="$(configured_value fork_remote)"
  UPSTREAM_REMOTE="$(configured_value upstream_remote)"
  UPSTREAM_BASE="$(configured_value upstream_base)"
  report stack_configuration ok \
    "resolved: fork '${FORK_REMOTE}', upstream '${UPSTREAM_REMOTE}/${UPSTREAM_BASE}'"
else
  report stack_configuration needs-setup \
    "could not resolve the layered configuration - fix the checks above first"
fi

# remote_check: reports whether one configured remote resolves in this clone,
# and its URL as context, or that neither could be checked. Both rows are
# printed either way, so the report always has the same shape.
remote_check() {
  local check="$1" remote_name="$2" description="$3"
  if [ "${CONFIGURATION_RESOLVED}" != "1" ]; then
    report "${check}" needs-setup "not checked - the configuration that names the ${description} could not be resolved"
    report "${check}_url" info "not checked"
    return
  fi
  if git remote get-url "${remote_name}" > /dev/null 2>&1; then
    report "${check}" ok "the ${description} '${remote_name}' is a remote in this clone"
    report "${check}_url" info "$(git remote get-url "${remote_name}")"
  else
    report "${check}" needs-setup \
      "the configuration names '${remote_name}' as the ${description}, but this clone has no such remote - add it, or override the name in ${PERSONAL_STACK_CONFIG_PATH}"
    report "${check}_url" info "not resolvable: '${remote_name}' is not a remote here"
  fi
}

remote_check fork_remote "${FORK_REMOTE:-}" "fork remote"
remote_check upstream_remote "${UPSTREAM_REMOTE:-}" "upstream remote"

# The merged-by-ancestry test every phase of the Routine depends on compares
# against <upstream_remote>/<upstream_base>, so a base branch that isn't there
# makes every branch look unmerged rather than failing loudly.
if [ "${CONFIGURATION_RESOLVED}" != "1" ]; then
  report upstream_base needs-setup "not checked - the configuration that names it could not be resolved"
elif git ls-remote --exit-code --heads "${UPSTREAM_REMOTE}" "${UPSTREAM_BASE}" > /dev/null 2>&1; then
  report upstream_base ok "'${UPSTREAM_BASE}' is on '${UPSTREAM_REMOTE}'"
else
  report upstream_base needs-setup \
    "'${UPSTREAM_BASE}' was not found on '${UPSTREAM_REMOTE}' - the merged-by-ancestry test compares against it, so every branch would read as unmerged"
fi

# %% the per-user override

if fetch_personal_notes_branch && git cat-file -e "FETCH_HEAD:${PERSONAL_STACK_CONFIG_PATH}" 2> /dev/null; then
  report personal_stack_config info "${PERSONAL_STACK_CONFIG_PATH} on '${NOTES_BRANCH}' is layered over the committed defaults"
else
  report personal_stack_config info "no personal override - the committed defaults in ${STACK_CONFIG_FILE} apply as-is"
fi

# %% the board

if git check-ignore --quiet "${STACK_BOARD_FILE}" 2> /dev/null; then
  report board_ignored ok "${STACK_BOARD_FILE} is gitignored, so a snapshot can never be committed"
else
  report board_ignored needs-setup \
    "${STACK_BOARD_FILE} is not gitignored here - the Routine rewrites it every run, so it would show up as a working-tree change on every branch"
fi

if [ -f "${STACK_BOARD_FILE}" ]; then
  report board_snapshot info "${STACK_BOARD_FILE} is present; stack.py status reads it"
else
  report board_snapshot info "no ${STACK_BOARD_FILE} yet - normal, the Routine writes one on its next run"
fi

exit "${EXIT_CODE}"
