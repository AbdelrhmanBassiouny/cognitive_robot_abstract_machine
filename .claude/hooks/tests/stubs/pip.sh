#!/bin/bash
set -uo pipefail

# Test stub standing in for `pip`, so the hook tests can exercise
# setup-personal-notes.sh's behaviour when installing the plan-dashboard
# dependencies fails - without a network, and without touching the interpreter
# actually running the tests. Copied into place as an executable named `pip`,
# earlier on PATH than the real one; see stub_executables.py.
#
#   STUB_PIP_EXIT_CODE  - the status to exit with (default 1, i.e. a failure)
#   STUB_PIP_CALL_LOG   - file every invocation is appended to

if [ -n "${STUB_PIP_CALL_LOG:-}" ]; then
  printf '%s\n' "$*" >> "${STUB_PIP_CALL_LOG}"
fi

STUB_EXIT_CODE="${STUB_PIP_EXIT_CODE:-1}"
if [ "${STUB_EXIT_CODE}" != "0" ]; then
  echo "stub pip: could not install (no network in this test)" >&2
fi
exit "${STUB_EXIT_CODE}"
