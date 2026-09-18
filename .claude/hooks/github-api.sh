#!/bin/bash

# The GitHub lookups the setup tooling needs, in one place: who the caller is
# authenticated as, which repository a remote points at, and whether a pull
# request label exists (creating it on request).
#
# Usage - sourced, not executed:
#   source "$CLAUDE_PROJECT_DIR/.claude/hooks/github-api.sh"
#   login="$(github_authenticated_login)"
#   github_repository_has_label octo-org/octo-repo merged || ...
#
# These were long assumed to need a Claude Code session, on the grounds that
# only a session's MCP tools can reach GitHub. They don't: `GET /user` and
# `GET /repos/{owner}/{repo}/labels/{name}` answer exactly the same questions
# from a shell, which is what lets ./setup-personal-notes.sh run with no
# session at all.
#
# Two backends, in order: the `gh` CLI when it's installed, since it already
# owns credential storage and refresh; otherwise GH_TOKEN or GITHUB_TOKEN with
# curl. With neither, every call that needs GitHub fails with a message naming
# both routes rather than guessing or silently reporting nothing.
#
# Parses JSON through python3 (already required by ./check-setup.sh) rather than
# adding a jq dependency, and only where a field is genuinely needed - label
# existence is an HTTP status code, so it needs no parsing at all.

GITHUB_API_BASE_URL="https://api.github.com"

# %% credentials

# github_api_token: prints GH_TOKEN, else GITHUB_TOKEN, and fails with the
# message naming both routes if neither is set. The single place that message
# lives, so all three callers below report a missing credential identically.
github_api_token() {
  local token="${GH_TOKEN:-${GITHUB_TOKEN:-}}"
  if [ -z "${token}" ]; then
    echo "No GitHub credentials available. Either install the 'gh' CLI and run" >&2
    echo "'gh auth login', or set GH_TOKEN or GITHUB_TOKEN to a token with access" >&2
    echo "to the repository." >&2
    return 1
  fi
  printf '%s' "${token}"
}

# github_authenticated_login: prints the login of whoever the credentials belong
# to - the answer to "is this remote really mine?", which a git remote URL alone
# can never give.
github_authenticated_login() {
  if command -v gh > /dev/null 2>&1; then
    gh api user --jq .login
    return
  fi

  local token
  token="$(github_api_token)" || return 1
  curl -sS \
      -H "Authorization: Bearer ${token}" \
      -H "Accept: application/vnd.github+json" \
      "${GITHUB_API_BASE_URL}/user" \
    | python3 -c 'import json, sys; print(json.load(sys.stdin)["login"])'
}

# %% remotes

# github_repository_of_remote: prints the "owner/repo" a remote refers to, given
# either a remote name already in this clone or a raw URL - the same two forms
# every setting in ./resolve-personal-notes-config.sh accepts. Handles the https,
# scp-style ssh and ssh:// spellings git itself accepts.
#
# Reads the trailing two path segments rather than matching a github.com host,
# because a Claude Code cloud session's clone legitimately has neither: its
# remote is rewritten through a local git proxy
# (http://local_proxy@127.0.0.1:<port>/git/<owner>/<repo>), and requiring the
# real host would fail in the environment this tooling is most used in.
github_repository_of_remote() {
  local remote="$1" remote_url owner repository
  remote_url="$(git remote get-url "${remote}" 2> /dev/null || printf '%s' "${remote}")"

  # Only a remote URL can be attributed to a GitHub account. A local path ends in
  # segments that look just like "<owner>/<repo>", so accepting one would report a
  # directory name as an account - and a caller comparing that against a real login
  # would refuse a valid setup.
  case "${remote_url}" in
    *://* | *@*:*) ;;
    *)
      echo "Cannot tell which GitHub repository '${remote}' refers to: it is neither a" >&2
      echo "remote in this clone nor a remote URL." >&2
      return 1
      ;;
  esac

  remote_url="${remote_url%/}"
  remote_url="${remote_url%.git}"
  # scp-style "git@host:owner/repo" is the one form separating host from path
  # with ':' instead of '/'; normalize it so one parse handles every spelling.
  case "${remote_url}" in
    *://*) ;;
    *) remote_url="${remote_url/://}" ;;
  esac

  case "${remote_url}" in
    */*) ;;
    *)
      echo "Could not read an owner and repository out of '${remote_url}'." >&2
      return 1
      ;;
  esac

  repository="${remote_url##*/}"
  owner="${remote_url%/*}"
  owner="${owner##*/}"

  if [ -z "${owner}" ] || [ -z "${repository}" ]; then
    echo "Could not read an owner and repository out of '${remote_url}'." >&2
    return 1
  fi
  printf '%s/%s\n' "${owner}" "${repository}"
}

# %% labels

# github_repository_has_label: succeeds when the label exists on the repository.
# A 404 is the answer, not an error - hence the status code rather than the body.
github_repository_has_label() {
  local repository="$1" label="$2"

  if command -v gh > /dev/null 2>&1; then
    gh api "repos/${repository}/labels/${label}" --silent > /dev/null 2>&1
    return
  fi

  local token status_code
  token="$(github_api_token)" || return 1
  status_code="$(curl -sS -o /dev/null -w '%{http_code}' \
    -H "Authorization: Bearer ${token}" \
    -H "Accept: application/vnd.github+json" \
    "${GITHUB_API_BASE_URL}/repos/${repository}/labels/${label}")"
  [ "${status_code}" = "200" ]
}

# github_create_label: creates the label, failing with whatever the API said if
# it refuses. A token may read a repository without being allowed to write its
# labels, so the caller has to be able to report that truthfully rather than
# assume the call worked.
github_create_label() {
  local repository="$1" label="$2" description="$3"

  if command -v gh > /dev/null 2>&1; then
    gh api --method POST "repos/${repository}/labels" \
      -f "name=${label}" -f "description=${description}" > /dev/null
    return
  fi

  local token payload status_code
  token="$(github_api_token)" || return 1
  payload="$(python3 -c \
    'import json, sys; print(json.dumps({"name": sys.argv[1], "description": sys.argv[2]}))' \
    "${label}" "${description}")"
  status_code="$(curl -sS -o /dev/null -w '%{http_code}' -X POST \
    -H "Authorization: Bearer ${token}" \
    -H "Accept: application/vnd.github+json" \
    -d "${payload}" \
    "${GITHUB_API_BASE_URL}/repos/${repository}/labels")"
  if [ "${status_code}" != "201" ]; then
    echo "GitHub refused to create the '${label}' label on ${repository} (HTTP ${status_code})." >&2
    return 1
  fi
}
