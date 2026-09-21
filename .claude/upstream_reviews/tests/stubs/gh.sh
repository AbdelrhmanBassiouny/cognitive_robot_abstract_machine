#!/bin/bash
set -uo pipefail

# Test stub standing in for the `gh` CLI, so the transport's success and
# failure paths can be exercised without reaching GitHub. Copied into place as
# an executable named `gh`, earlier on PATH than any real one - see the
# stubbed_gh fixture in test_upstream_reviews.py.
#
# Recognizes the two calls the transport makes, `gh api graphql --input -` and
# `gh api --allow-escape-sequences <endpoint>`:
#   STUB_GH_GRAPHQL_JSON - the JSON body to print
#   STUB_GH_JOB_LOG      - the job log to print for the endpoint call
#   STUB_GH_EXIT_CODE    - the exit code to return, defaulting to 0
#   STUB_GH_CALL_LOG     - file the request body, or the endpoint asked for, is
#                          appended to, so a test can assert the exact call sent
#
# The escape-sequences flag is matched rather than skipped over: gh returns a
# coloured log and then declines to print it without that flag, so a transport
# that stopped passing it must fail here rather than pass.
#
# Exits 64 on an invocation it doesn't recognize, rather than a plausible-
# looking success: a test must fail loudly if the transport changes the call it
# makes.

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

if [ "${1:-}" = "api" ] && [ "${2:-}" = "--allow-escape-sequences" ]; then
  if [ -n "${STUB_GH_CALL_LOG:-}" ]; then
    printf '%s\n' "${3:-}" >> "${STUB_GH_CALL_LOG}"
  fi
  EXIT_CODE="${STUB_GH_EXIT_CODE:-0}"
  if [ "${EXIT_CODE}" -ne 0 ]; then
    echo "stub gh: simulated failure" >&2
    exit "${EXIT_CODE}"
  fi
  printf '%s' "${STUB_GH_JOB_LOG:-}"
  exit 0
fi

echo "stub gh: unexpected invocation: $*" >&2
exit 64
