#!/bin/bash
set -uo pipefail

# Test stub standing in for `curl`, so the hook tests can exercise github-api.sh's
# token fallback - the path taken when `gh` isn't installed - without reaching
# GitHub. Copied into place as an executable named `curl`, earlier on PATH than
# the real one; see stub_executables.py.
#
# Recognizes only the three request shapes github-api.sh makes, and answers them
# from the environment:
#   STUB_CURL_LOGIN              - the login GET /user reports
#   STUB_CURL_MISSING_LABELS     - space-separated labels that answer 404
#   STUB_CURL_CREATE_LABEL_STATUS - the status a label POST answers (default 201)
#   STUB_CURL_CALL_LOG           - file every invocation is appended to
#
# Exits 64 on an unrecognized invocation for the same reason gh.sh does: a
# changed call must fail a test rather than pass by accident.

if [ -n "${STUB_CURL_CALL_LOG:-}" ]; then
  printf '%s\n' "$*" >> "${STUB_CURL_CALL_LOG}"
fi

REQUEST_URL=""
REQUEST_METHOD="GET"
PREVIOUS_ARGUMENT=""
for argument in "$@"; do
  [ "${PREVIOUS_ARGUMENT}" != "-X" ] || REQUEST_METHOD="${argument}"
  case "${argument}" in
    https://*) REQUEST_URL="${argument}" ;;
  esac
  PREVIOUS_ARGUMENT="${argument}"
done

if [ -z "${REQUEST_URL}" ]; then
  echo "stub curl: no URL in invocation: $*" >&2
  exit 64
fi

if [ "${REQUEST_METHOD}" = "POST" ]; then
  printf '%s' "${STUB_CURL_CREATE_LABEL_STATUS:-201}"
  exit 0
fi

case "${REQUEST_URL}" in
  */user)
    printf '{"login":"%s","type":"User"}\n' "${STUB_CURL_LOGIN:-stub-user}"
    exit 0
    ;;
  */labels/*)
    requested_label="${REQUEST_URL##*/}"
    for missing_label in ${STUB_CURL_MISSING_LABELS:-}; do
      if [ "${requested_label}" = "${missing_label}" ]; then
        printf '404'
        exit 0
      fi
    done
    printf '200'
    exit 0
    ;;
esac

echo "stub curl: unexpected URL: ${REQUEST_URL}" >&2
exit 64
