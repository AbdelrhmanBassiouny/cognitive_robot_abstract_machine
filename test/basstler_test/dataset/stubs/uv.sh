#!/bin/bash
set -uo pipefail

# Test stub standing in for `uv`, so session-start.sh's tests can exercise the
# environment it creates without fetching or creating a real interpreter.
# Copied into place as an executable named `uv`, earlier on PATH than any real
# one; see the stub_bin fixture in conftest.py.
#
# Recognizes only `venv --python <requirement> <directory>`, the one invocation
# create_basstler_environment makes, and writes <directory>/bin/python as a
# script running STUB_UV_PYTHON - the interpreter running the suite.
#   STUB_UV_CALL_LOG - file the invocation is appended to
#   STUB_UV_STATUS   - exit status to report, default 0; anything else creates
#                      nothing
#
# Exits 64 on an unrecognized invocation for the same reason gh.sh does: a
# changed call must fail a test rather than pass by accident.

if [ -n "${STUB_UV_CALL_LOG:-}" ]; then
  printf '%s\n' "$*" >> "${STUB_UV_CALL_LOG}"
fi

if [ "${1:-}" != "venv" ] || [ "${2:-}" != "--python" ] || [ -z "${3:-}" ] \
    || [ -z "${4:-}" ]; then
  echo "uv stub: unrecognized invocation: $*" >&2
  exit 64
fi

STATUS="${STUB_UV_STATUS:-0}"
if [ "${STATUS}" != "0" ]; then
  echo "error: stub uv found no interpreter satisfying $3" >&2
  exit "${STATUS}"
fi

mkdir -p "$4/bin"
printf '#!/bin/sh\nexec "%s" "$@"\n' "${STUB_UV_PYTHON}" > "$4/bin/python"
chmod +x "$4/bin/python"
echo "Creating virtual environment at: $4"
