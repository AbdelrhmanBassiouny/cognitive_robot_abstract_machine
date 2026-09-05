#!/bin/bash
set -euo pipefail

# Stands in for refresh_dashboard.sh in build_site.py's tests: writes the page it was
# asked for, records what it was handed beside that page, and prints the summary shape
# the real script prints. The real script's own orchestration is covered by
# test_refresh_dashboard_sh.py, so none of it is reproduced here.

STUB_DIRECTORY="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec python3 "${STUB_DIRECTORY}/record_refresh_arguments.py" "$@"
