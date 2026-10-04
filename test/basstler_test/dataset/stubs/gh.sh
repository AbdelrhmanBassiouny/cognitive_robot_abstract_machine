#!/bin/bash
set -uo pipefail

# Test stub standing in for the `gh` CLI, so every caller that shells out to it can be
# exercised without reaching GitHub and without credentials. Copied into place as an
# executable named `gh`, earlier on PATH than any real one - see executable_stubs.py,
# the stub_bin fixture in test_plan_updates_since_sh.py and the stubbed_gh fixture in
# test_upstream_reviews.py.
#
# One stub rather than one per suite: the recognized invocations are disjoint, and a
# second copy is what drifts when the contract moves. Driven entirely by the
# environment, so a test declares the GitHub state it wants rather than patching this
# file.
#
# `gh api graphql --input -`, the one call upstream_reviews' transport makes:
#   STUB_GH_GRAPHQL_JSON - the JSON body to print
#   STUB_GH_EXIT_CODE    - the exit code to return, defaulting to 0
#   STUB_GH_CALL_LOG     - file the request body is appended to, so a test can
#                          assert the exact query and variables sent
#
# `gh api --paginate repos/<owner>/<repo>/issues/<n>/comments?...`, the one call
# plan-updates-since.sh makes through this backend:
#   STUB_GH_ISSUE_COMMENTS_JSON - the JSON body to print
#
# `gh api user`, and label read and create, the calls github-api.sh makes:
#   STUB_GH_LOGIN              - the login `gh api user` reports
#   STUB_GH_MISSING_LABELS     - space-separated labels that answer 404
#   STUB_GH_CREATE_LABEL_FAILS - set to 1 to make label creation fail
#
# Every call but the graphql one is appended to STUB_GH_CALL_LOG, when set, so a test
# can assert which calls were made.
#
# Exits 64 on an invocation it doesn't recognize, rather than a plausible-looking
# success: a test must fail loudly if a caller changes the call it makes.

if [ "${1:-}" = "api" ] && [ "${2:-}" = "graphql" ] && [ "${3:-}" = "--input" ]; then
  REQUEST_BODY="$(cat)"
  if [ -n "${STUB_GH_CALL_LOG:-}" ]; then
    printf '%s\n' "${REQUEST_BODY}" >> "${STUB_GH_CALL_LOG}"
  fi
  EXIT_CODE="${STUB_GH_EXIT_CODE:-0}"
  if [ "${EXIT_CODE}" -ne 0 ]; then
    echo "stub gh: simulated failure" >&2
    exit "${EXIT_CODE}"
  fi
  printf '%s' "${STUB_GH_GRAPHQL_JSON:-{\}}"
  exit 0
fi

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
