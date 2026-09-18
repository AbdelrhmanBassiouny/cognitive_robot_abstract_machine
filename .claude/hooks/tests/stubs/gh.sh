#!/bin/bash
set -uo pipefail

# Test stub standing in for the `gh` CLI, so the hook tests can exercise the
# backends that would otherwise reach GitHub - without a network and without
# credentials. Copied into place as an executable named `gh`, earlier on PATH
# than any real one; see stub_executables.py and the stub_bin fixture in
# test_plan_updates_since_sh.py.
#
# Serves two callers with disjoint calls, so one stub covers both rather than
# two files racing for the same name on PATH:
#   github-api.sh          - the authenticated login, and label read/create
#   plan-updates-since.sh  - a plan tracking issue's comments
#
# Driven entirely by the environment, so a test declares the GitHub state it
# wants rather than patching this file:
#   STUB_GH_LOGIN                - the login `gh api user` reports
#   STUB_GH_MISSING_LABELS       - space-separated labels that answer 404
#   STUB_GH_CREATE_LABEL_FAILS   - set to 1 to make label creation fail
#   STUB_GH_ISSUE_COMMENTS_JSON  - the JSON body the comments call prints
#   STUB_GH_CALL_LOG             - file every invocation is appended to, so a
#                                  test can assert which calls were made
#
# Exits 64 on an invocation it doesn't recognize, rather than a plausible-looking
# success: a test must fail loudly when a caller changes the call it makes.

if [ -n "${STUB_GH_CALL_LOG:-}" ]; then
  printf '%s\n' "$*" >> "${STUB_GH_CALL_LOG}"
fi

if [ "${1:-}" != "api" ]; then
  echo "stub gh: unexpected invocation: $*" >&2
  exit 64
fi

# `gh api user --jq .login`
if [ "${2:-}" = "user" ]; then
  printf '%s\n' "${STUB_GH_LOGIN:-stub-user}"
  exit 0
fi

# `gh api --paginate repos/<owner>/<repo>/issues/<n>/comments?...`
if [ "${2:-}" = "--paginate" ]; then
  case "${3:-}" in
    repos/*/issues/*/comments\?*)
      printf '%s' "${STUB_GH_ISSUE_COMMENTS_JSON:-[]}"
      exit 0
      ;;
  esac
fi

# `gh api --method POST repos/<owner>/<repo>/labels -f name=<label> ...`
if [ "${2:-}" = "--method" ] && [ "${3:-}" = "POST" ]; then
  if [ "${STUB_GH_CREATE_LABEL_FAILS:-0}" = "1" ]; then
    echo "stub gh: 403 Forbidden - the token may not create labels" >&2
    exit 1
  fi
  exit 0
fi

# `gh api repos/<owner>/<repo>/labels/<label> --silent`
case "${2:-}" in
  repos/*/labels/*)
    requested_label="${2##*/}"
    for missing_label in ${STUB_GH_MISSING_LABELS:-}; do
      if [ "${requested_label}" = "${missing_label}" ]; then
        echo "stub gh: 404 Not Found ($2)" >&2
        exit 1
      fi
    done
    exit 0
    ;;
esac

echo "stub gh: unexpected invocation: $*" >&2
exit 64
