#!/bin/bash
set -euo pipefail

# The whole stacked-PR setup, non-interactively: name the fork and upstream
# remotes the configuration expects, record any per-user overrides on the
# personal-notes branch, check the pull request labels the workflow reads and
# writes, optionally install the tooling onto a fork-overlay branch, and print
# the Routine prompt to paste.
#
# Usage (from anywhere - always operates on this repo specifically, see
# ./resolve-personal-notes-config.sh):
#   ./.claude/hooks/setup-stacked-prs.sh --fork <name-or-url> --upstream <name-or-url> \
#     [--mode native|fork-overlay] [--overlay-branch <name>] \
#     [--personal-config <key>=<value>]... [--create-labels]
#
#   --fork            Required: your fork, which holds the full stack. Required
#                     rather than guessed for the same reason --remote is in
#                     ./setup-personal-notes.sh - a wrong guess points the stack
#                     at a repository you don't control.
#   --upstream        Required: the slow review repository the stack promotes to.
#   --mode            native (default): the tooling is tracked on this repo's own
#                     default branch. fork-overlay: it isn't, and this installs it
#                     onto a never-merged branch of your fork instead.
#   --overlay-branch  The fork-overlay branch name. Defaults to claude/stack-tooling.
#   --personal-config Override one setting for yourself only, e.g. fork_remote=my-fork.
#                     Written to the personal-notes branch, never to the committed
#                     defaults. Repeatable. A value equal to the committed default
#                     is dropped rather than written.
#   --create-labels   Create whichever of the workflow's labels the fork is missing.
#                     Off by default: labels are visible to everyone who can see the
#                     repository.
#
# Safe to re-run: every step is skipped when ./check-stack-setup.sh already
# reports it done, and the writes to the personal-notes and overlay branches are
# no-ops when nothing changed. Exits with check-stack-setup.sh's own status, so a
# setup that only half worked is never reported as success.
#
# /setup-stacked-prs wraps this script with the questions it can ask a person and
# answer for them; nothing here needs a Claude Code session - see ./github-api.sh
# on why the GitHub steps don't either.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/resolve-personal-notes-config.sh"
source "${GITHUB_API_SCRIPT}"

DEFAULT_OVERLAY_BRANCH="claude/stack-tooling"

# The tooling a fork-overlay branch has to carry to be self-sufficient: the stack
# tooling itself, plus the hooks that resolve its paths, reach GitHub, and set it
# up again on the next clone.
OVERLAY_FILES=(
  "${STACK_SCRIPT}"
  "${STACK_CONFIG_FILE}"
  "${STACK_README_FILE}"
  "${STACK_ROUTINE_DOCUMENT}"
  "${STACK_ROUTINE_PROMPT_FILE}"
  "${SCRIPT_DIR}/resolve-personal-notes-config.sh"
  "${GITHUB_API_SCRIPT}"
  "${WRITE_BRANCH_FILES_SCRIPT}"
  "${CHECK_STACK_SETUP_SCRIPT}"
  "${SETUP_STACKED_PRS_SCRIPT}"
)

usage() {
  echo "Usage: ${BASH_SOURCE[0]} --fork <name-or-url> --upstream <name-or-url>" >&2
  echo "         [--mode native|fork-overlay] [--overlay-branch <name>]" >&2
  echo "         [--personal-config <key>=<value>]... [--create-labels]" >&2
}

# %% arguments

FORK=""
UPSTREAM=""
INSTALL_MODE="native"
OVERLAY_BRANCH="${DEFAULT_OVERLAY_BRANCH}"
CREATE_MISSING_LABELS=0
PERSONAL_CONFIG_ENTRIES=()

while [ $# -gt 0 ]; do
  case "$1" in
    --fork)
      FORK="${2:-}"
      shift 2
      ;;
    --upstream)
      UPSTREAM="${2:-}"
      shift 2
      ;;
    --mode)
      INSTALL_MODE="${2:-}"
      shift 2
      ;;
    --overlay-branch)
      OVERLAY_BRANCH="${2:-}"
      shift 2
      ;;
    --personal-config)
      PERSONAL_CONFIG_ENTRIES+=("${2:-}")
      shift 2
      ;;
    --create-labels)
      CREATE_MISSING_LABELS=1
      shift
      ;;
    *)
      echo "Unrecognized argument: $1" >&2
      usage
      exit 1
      ;;
  esac
done

if [ -z "${FORK}" ]; then
  echo "--fork is required: name the repository that holds your stack." >&2
  echo "It is not guessed, because a wrong guess points the whole workflow at a" >&2
  echo "repository you may not own." >&2
  usage
  exit 1
fi
if [ -z "${UPSTREAM}" ]; then
  echo "--upstream is required: name the repository your stack is reviewed in." >&2
  usage
  exit 1
fi
case "${INSTALL_MODE}" in
  native | fork-overlay) ;;
  *)
    echo "--mode must be 'native' or 'fork-overlay', not: ${INSTALL_MODE}" >&2
    usage
    exit 1
    ;;
esac

# %% the per-user overrides, applied before anything reads the configuration

# resolved_setting: prints one value from stack.py's own layered resolution, so
# nothing here re-implements "personal override beats committed default".
resolved_setting() {
  python3 "${STACK_SCRIPT}" config | awk -F'\t' -v name="$1" '$1 == name { print $2; exit }'
}

# committed_setting: prints one value from the committed defaults alone, which is
# what an override has to differ from to be worth recording.
committed_setting() {
  python3 - "${STACK_CONFIG_FILE}" "$1" <<'PYTHON'
import sys
import tomllib

with open(sys.argv[1], "rb") as committed_defaults:
    print(tomllib.load(committed_defaults).get(sys.argv[2], ""))
PYTHON
}

# write_personal_config: records the overrides that actually differ from the
# committed defaults onto the personal-notes branch. Writes nothing when every
# value given already matches - a file full of restated defaults is drift waiting
# to happen.
write_personal_config() {
  local entry key value overrides="" scratch_file
  for entry in "${PERSONAL_CONFIG_ENTRIES[@]}"; do
    case "${entry}" in
      *=*) ;;
      *)
        echo "--personal-config takes <key>=<value>, not: ${entry}" >&2
        exit 1
        ;;
    esac
    key="${entry%%=*}"
    value="${entry#*=}"

    if ! python3 "${STACK_SCRIPT}" config | grep -q "^${key}	"; then
      echo "Not a stack setting: ${key}" >&2
      echo "Known settings: $(python3 "${STACK_SCRIPT}" config | cut -f1 | tr '\n' ' ')" >&2
      exit 1
    fi
    if [ "${value}" = "$(committed_setting "${key}")" ]; then
      echo "'${key}' already defaults to '${value}' - not recording an override for it."
      continue
    fi
    overrides="${overrides}${key} = \"${value}\""$'\n'
  done

  if [ -z "${overrides}" ]; then
    return 0
  fi

  scratch_file="$(mktemp)"
  printf '%s' "${overrides}" > "${scratch_file}"
  bash "${WRITE_PERSONAL_NOTES_FILE_SCRIPT}" \
    --source "${scratch_file}" \
    --destination "${PERSONAL_STACK_CONFIG_PATH}" \
    --message "Record personal stacked-PR configuration"
  rm -f "${scratch_file}"
}

if [ ${#PERSONAL_CONFIG_ENTRIES[@]} -gt 0 ]; then
  write_personal_config
fi

FORK_REMOTE="$(resolved_setting fork_remote)"
UPSTREAM_REMOTE="$(resolved_setting upstream_remote)"
UPSTREAM_BASE="$(resolved_setting upstream_base)"

# %% the remotes

# name_remote: makes the configured remote name resolve to what was asked for.
# Only ever adds a remote that is missing - repointing an existing one is the
# kind of change that silently redirects pushes, so it is reported instead.
name_remote() {
  local remote_name="$1" target="$2" description="$3" existing_url
  if existing_url="$(git remote get-url "${remote_name}" 2> /dev/null)"; then
    if [ "${existing_url}" = "${target}" ] || [ "${remote_name}" = "${target}" ]; then
      echo "The ${description} '${remote_name}' already points at ${existing_url}."
      return 0
    fi
    echo "The ${description} '${remote_name}' already points at ${existing_url}, not"
    echo "'${target}' - left as it is. Change it yourself if that is wrong:"
    echo "  git remote set-url ${remote_name} ${target}"
    return 0
  fi

  if git remote get-url "${target}" > /dev/null 2>&1; then
    target="$(git remote get-url "${target}")"
  fi
  git remote add "${remote_name}" "${target}"
  echo "Added the ${description} '${remote_name}' -> ${target}."
}

name_remote "${FORK_REMOTE}" "${FORK}" "fork remote"
name_remote "${UPSTREAM_REMOTE}" "${UPSTREAM}" "upstream remote"

# %% is the fork really yours?

# verify_fork_owner: fails only when GitHub positively says the fork belongs to
# somebody else. Anything less certain - an unparseable remote, no credentials -
# is reported and allowed, because --fork named it explicitly.
verify_fork_owner() {
  local repository owner login
  if ! repository="$(github_repository_of_remote "${FORK_REMOTE}" 2> /dev/null)"; then
    echo "Could not tell which GitHub repository '${FORK_REMOTE}' is, so its owner was"
    echo "not verified. That is expected for a local path or a non-GitHub remote."
    return 0
  fi

  owner="${repository%%/*}"
  if ! login="$(github_authenticated_login 2> /dev/null)"; then
    echo "Could not verify that '${owner}' is you: no GitHub credentials available."
    echo "Continuing, since --fork named that repository explicitly."
    return 0
  fi

  if [ "${owner}" != "${login}" ]; then
    echo "Refusing to set up the stack on '${repository}': it is owned by '${owner}'," >&2
    echo "but you are authenticated as '${login}'. The stack lives on a fork you own -" >&2
    echo "pass --fork for your own fork instead." >&2
    return 1
  fi

  echo "Fork '${repository}' is owned by '${login}'."
}

verify_fork_owner

# The merged-by-ancestry test compares against <upstream_remote>/<upstream_base>,
# so fetch it now rather than leaving the first Routine run to discover it.
if git fetch "${UPSTREAM_REMOTE}" "${UPSTREAM_BASE}" --quiet 2> /dev/null; then
  echo "Fetched '${UPSTREAM_BASE}' from '${UPSTREAM_REMOTE}'."
else
  echo "Could not fetch '${UPSTREAM_BASE}' from '${UPSTREAM_REMOTE}' - the merged check"
  echo "compares against it, so this needs to work before the workflow does."
fi

# %% the fork-overlay install

if [ "${INSTALL_MODE}" = "fork-overlay" ]; then
  OVERLAY_FILE_ARGUMENTS=()
  for overlay_file in "${OVERLAY_FILES[@]}"; do
    # Destinations are the repo-relative paths; a source given as an absolute
    # path (the hooks directory this script resolved for itself) still lands at
    # the same place in the tree.
    OVERLAY_FILE_ARGUMENTS+=(--file "${overlay_file}:${overlay_file#"${PROJECT_ROOT}/"}")
  done
  bash "${WRITE_BRANCH_FILES_SCRIPT}" \
    --remote "${FORK_REMOTE}" \
    --branch "${OVERLAY_BRANCH}" \
    --message "Install the stacked-PR tooling" \
    --create-branch-if-absent \
    "${OVERLAY_FILE_ARGUMENTS[@]}"
  echo "Re-run this in fork-overlay mode whenever the tooling changes - that is the update."
else
  echo "Native install: the tooling is tracked on this repository's own default branch."
fi

# %% the pull request labels the workflow reads and writes

# label_description: what each label means, so a created one explains itself to
# everyone who later sees it in the repository.
label_description() {
  case "$1" in
    "${IN_REVIEW_LABEL}") printf 'Promoted to the upstream review queue' ;;
    "${REBASE_LABEL}") printf 'Restack this branch by rebasing instead of merging' ;;
    "${NEEDS_RESOLUTION_LABEL}") printf 'A restack conflict or CI failure is waiting on its author' ;;
    "${CRAM2_LINK_SENT_LABEL}") printf 'The upstream create-link was sent and not yet acted on' ;;
    *) printf 'Used by this repository stacked-PR workflow' ;;
  esac
}

IN_REVIEW_LABEL="$(resolved_setting in_review_label)"
REBASE_LABEL="$(resolved_setting rebase_label)"
NEEDS_RESOLUTION_LABEL="$(resolved_setting needs_resolution_label)"
CRAM2_LINK_SENT_LABEL="$(resolved_setting cram2_link_sent_label)"
WORKFLOW_LABELS=(
  "${IN_REVIEW_LABEL}"
  "${REBASE_LABEL}"
  "${NEEDS_RESOLUTION_LABEL}"
  "${CRAM2_LINK_SENT_LABEL}"
)

# check_workflow_labels: reports which of the labels this workflow reads and
# writes are missing from the fork, creating them only when asked. Never fatal: a
# missing label blocks nothing else in this setup, though the Routine's first
# label write would fail on one.
check_workflow_labels() {
  local repository label missing_labels=()

  if ! repository="$(github_repository_of_remote "${FORK_REMOTE}" 2> /dev/null)"; then
    echo "Skipped the label check: could not tell which repository '${FORK_REMOTE}' refers to."
    return 0
  fi
  if ! github_authenticated_login > /dev/null 2>&1; then
    echo "Skipped the label check on '${repository}': no GitHub credentials available."
    return 0
  fi

  for label in "${WORKFLOW_LABELS[@]}"; do
    github_repository_has_label "${repository}" "${label}" || missing_labels+=("${label}")
  done

  if [ ${#missing_labels[@]} -eq 0 ]; then
    echo "Every label this workflow uses is present on '${repository}'."
    return 0
  fi

  echo "Missing labels on '${repository}': ${missing_labels[*]}"
  if [ "${CREATE_MISSING_LABELS}" != "1" ]; then
    echo "Not creating them - re-run with --create-labels to have them created."
    return 0
  fi

  for label in "${missing_labels[@]}"; do
    if github_create_label "${repository}" "${label}" "$(label_description "${label}")"; then
      echo "Created '${label}' on '${repository}'."
    else
      echo "Could not create '${label}' on '${repository}' - the error above says why." >&2
    fi
  done
}

check_workflow_labels

# %% the two things no command can finish

echo
echo "Paste this into claude.ai/code/routines as the Routine's prompt:"
echo
# The prompt lives in one canonical file; only the remote names are filled in.
sed -e "s|<FORK_REMOTE>|${FORK_REMOTE}|g" -e "s|<UPSTREAM_REMOTE>|${UPSTREAM_REMOTE}|g" \
  "${STACK_ROUTINE_PROMPT_FILE}"

echo
echo "To publish the board, create a stack-board repository of your own:"
echo "  1. Create an empty repository (any name; 'stack-board' by convention) and"
echo "     enable GitHub Pages on it."
echo "  2. Set its repository variables for the fork ('${FORK_REMOTE}'), the branch the"
echo "     board reads, and the upstream ('${UPSTREAM_REMOTE}')."
echo "  3. Add the publishing workflow. It is not shipped here yet - it arrives with the"
echo "     stack-board Pages work - so nothing was written to any other repository."

# %% the result

# Reports what is true now rather than what was intended, and its status becomes
# this script's - so a half-finished setup can never exit 0.
echo
echo "Setup complete. Final check:"
bash "${CHECK_STACK_SETUP_SCRIPT}"
