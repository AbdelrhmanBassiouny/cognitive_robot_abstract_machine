#!/bin/bash
set -euo pipefail

# The whole one-time personal-notes setup, non-interactively: point the notes
# remote at a repository you own, create the notes branch, optionally seed it,
# install the plan-dashboard dependencies, pick the notes up in this clone, and
# check the pull request labels the tooling uses.
#
# Usage (from anywhere - always operates on this repo specifically, see
# ./resolve-personal-notes-config.sh):
#   ./.claude/hooks/setup-personal-notes.sh --remote <name-or-url> \
#     [--name "Your Name" --email you@example.com] [--starter-notes] [--create-labels]
#
#   --remote          Required: the remote your notes belong on, as a remote name
#                     already in this clone or a raw URL. Required rather than
#                     guessed - guessing wrong pushes your notes to a repository
#                     you don't control, which is the one decision here that
#                     cannot be undone by re-running.
#   --name, --email   Your git identity, recorded on the notes branch so every
#                     clone authors its commits as you. Both or neither, and not
#                     guessed from this clone's git config for the reason
#                     ./save-git-identity.sh gives: in a session environment that
#                     config is the agent's identity, not yours. Omitting them
#                     leaves the identity unrecorded, which check-setup.sh then
#                     reports - and this script exits with its status.
#   --starter-notes   Seed a brand-new notes file from the starter template
#                     instead of leaving it empty.
#   --create-labels   Create any of the `merged`, `bug` and `in-review` labels
#                     that the repository is missing. Off by default: labels are
#                     visible to everyone who can see the repository.
#
# Safe to re-run: every step is skipped when ./check-setup.sh already reports it
# done, and the two that write to the notes branch are no-ops when nothing
# changed. Exits with check-setup.sh's own status, so a setup that only half
# worked is never reported as success.
#
# /setup-personal-notes wraps this script with the questions it can ask a person
# and answer for them; nothing here needs a Claude Code session - see
# ./github-api.sh on why the GitHub steps don't either.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/resolve-personal-notes-config.sh"
# Every path below comes from the constants that file defines, and it has already
# cd'd to the project root they are relative to.
source "${GITHUB_API_SCRIPT}"

usage() {
  echo "Usage: ${BASH_SOURCE[0]} --remote <name-or-url>" \
    "[--name \"Your Name\" --email you@example.com] [--starter-notes] [--create-labels]" >&2
}

# %% arguments

CHOSEN_REMOTE=""
IDENTITY_NAME=""
IDENTITY_EMAIL=""
SEED_STARTER_NOTES=0
CREATE_MISSING_LABELS=0
while [ $# -gt 0 ]; do
  case "$1" in
    --remote)
      if [ $# -lt 2 ]; then
        echo "--remote needs a value: a remote name or a URL." >&2
        usage
        exit 1
      fi
      CHOSEN_REMOTE="$2"
      shift 2
      ;;
    --name)
      if [ $# -lt 2 ]; then
        echo "--name needs a value: the name your commits should carry." >&2
        usage
        exit 1
      fi
      IDENTITY_NAME="$2"
      shift 2
      ;;
    --email)
      if [ $# -lt 2 ]; then
        echo "--email needs a value: the email your commits should carry." >&2
        usage
        exit 1
      fi
      IDENTITY_EMAIL="$2"
      shift 2
      ;;
    --starter-notes)
      SEED_STARTER_NOTES=1
      shift
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

if [ -z "${CHOSEN_REMOTE}" ]; then
  echo "--remote is required: name the remote your personal notes belong on." >&2
  echo "It is not guessed, because a wrong guess pushes your notes to a repository" >&2
  echo "you may not own." >&2
  usage
  exit 1
fi

# One half of an identity records nothing: git needs both to author a commit, and
# ./save-git-identity.sh refuses the pair anyway. Catching it here means the
# refusal comes before the branch is created rather than after.
if [ -n "${IDENTITY_NAME}${IDENTITY_EMAIL}" ] \
    && { [ -z "${IDENTITY_NAME}" ] || [ -z "${IDENTITY_EMAIL}" ]; }; then
  echo "--name and --email go together: a commit needs both to be authored." >&2
  usage
  exit 1
fi

# %% what is already done

git config claude.personalNotesRemote "${CHOSEN_REMOTE}"
# The resolved value is now the chosen one; every script invoked below re-reads it
# from git config for itself.
NOTES_REMOTE="${CHOSEN_REMOTE}"
echo "Notes remote set to '${NOTES_REMOTE}'."

# check-setup.sh is the single source of truth for what still needs doing, so
# each step below is gated on its verdict rather than on a second, independent
# check of the same thing. Its non-zero exit just means "something needs setup",
# which is the normal case here.
SETUP_REPORT="$(bash "${CHECK_SETUP_SCRIPT}" || true)"

# setup_check_status: prints the status check-setup.sh reported for one check.
setup_check_status() {
  printf '%s\n' "${SETUP_REPORT}" | awk -F'\t' -v check="$1" '$1 == check { print $2; exit }'
}

# %% is the notes remote really yours?

# verify_notes_remote_owner: fails only when GitHub positively says the notes
# remote belongs to somebody else. Anything less certain - an unparseable remote,
# no credentials - is reported and allowed, because --remote named it explicitly.
verify_notes_remote_owner() {
  local repository owner login
  if ! repository="$(github_repository_of_remote "${NOTES_REMOTE}" 2> /dev/null)"; then
    echo "Could not tell which GitHub repository '${NOTES_REMOTE}' is, so its owner was"
    echo "not verified. That is expected for a local path or a non-GitHub remote."
    return 0
  fi

  owner="${repository%%/*}"
  if ! login="$(github_authenticated_login 2> /dev/null)"; then
    echo "Could not verify that '${owner}' is you: no GitHub credentials available."
    echo "Continuing, since --remote named that repository explicitly."
    return 0
  fi

  if [ "${owner}" != "${login}" ]; then
    echo "Refusing to set up personal notes on '${repository}': it is owned by" >&2
    echo "'${owner}', but you are authenticated as '${login}'. Personal notes must" >&2
    echo "live on a repository you own - pass --remote for your own fork instead." >&2
    return 1
  fi

  echo "Notes remote '${repository}' is owned by '${login}'."
}

verify_notes_remote_owner

# %% the notes branch and its contents

if [ "$(setup_check_status notes_branch)" = "needs-setup" ]; then
  bash "${CREATE_PERSONAL_NOTES_BRANCH_SCRIPT}"
else
  echo "Notes branch '${NOTES_BRANCH}' already exists - left untouched."
fi

if [ "${SEED_STARTER_NOTES}" = "1" ]; then
  bash "${WRITE_PERSONAL_NOTES_FILE_SCRIPT}" \
    --source "${STARTER_NOTES_FILE}" \
    --destination "${NOTES_PATH}" \
    --message "Initialize personal notes from the starter template"
else
  echo "Left '${NOTES_PATH}' as it is - pass --starter-notes to seed it from the template."
fi

# %% the git identity every clone authors as

# Given none, this step does nothing and the final report says so - check-setup.sh's
# git_identity row already names both the identity commits carry today and the command
# that records one, so saying it a second time here would be the same message twice.
if [ -n "${IDENTITY_NAME}" ]; then
  bash "${SAVE_GIT_IDENTITY_SCRIPT}" --name "${IDENTITY_NAME}" --email "${IDENTITY_EMAIL}"
fi

# %% the plan-dashboard dependencies

if [ "$(setup_check_status dashboard_dependencies)" = "needs-setup" ]; then
  if pip install -r "${PLAN_DASHBOARD_REQUIREMENTS_FILE}"; then
    echo "Installed the plan-dashboard dependencies."
  else
    echo "Could not install the plan-dashboard dependencies. Re-run this by hand when"
    echo "you can: pip install -r ${PLAN_DASHBOARD_REQUIREMENTS_FILE}"
    echo "Everything except plan dashboards works without them; carrying on."
  fi
else
  echo "Plan-dashboard dependencies already installed."
fi

# %% pick the notes up in this clone

bash "${SESSION_START_SCRIPT}"

# %% the pull request labels the tooling applies

# label_description: what each label means, so a created one explains itself to
# everyone who later sees it in the repository.
label_description() {
  case "$1" in
    merged) printf 'The changes landed even though GitHub never recorded a merge' ;;
    bug) printf 'Fixes incorrect behaviour' ;;
    in-review) printf 'Waiting on review' ;;
    *) printf 'Used by this repository review workflow' ;;
  esac
}

# check_pull_request_labels: reports which of the labels this tooling reads and
# applies are missing from the repository pull requests are opened against,
# creating them only when asked. Never fatal: a missing label blocks nothing else
# in this setup.
check_pull_request_labels() {
  local repository label missing_labels=()

  if ! repository="$(github_repository_of_remote origin 2> /dev/null)"; then
    echo "Skipped the label check: could not tell which repository 'origin' refers to."
    return 0
  fi
  if ! github_authenticated_login > /dev/null 2>&1; then
    echo "Skipped the label check on '${repository}': no GitHub credentials available."
    return 0
  fi

  for label in "${PULL_REQUEST_LABELS[@]}"; do
    github_repository_has_label "${repository}" "${label}" || missing_labels+=("${label}")
  done

  if [ ${#missing_labels[@]} -eq 0 ]; then
    echo "Every label this tooling uses is present on '${repository}'."
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

check_pull_request_labels

# %% the result

# Reports what is true now rather than what was intended, and its status becomes
# this script's - so a half-finished setup can never exit 0.
echo
echo "Setup complete. Final check:"
bash "${CHECK_SETUP_SCRIPT}"
