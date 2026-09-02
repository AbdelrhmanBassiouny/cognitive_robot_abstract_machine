#!/bin/bash
# Stands in for refresh_dashboard.sh in the build_site tests: records its arguments,
# keeps a copy of the pull request data it was handed (the real file is a scratch
# path deleted after the run), writes a placeholder dashboard to --output, and prints
# the merged summary shape the real script prints.
set -euo pipefail

printf '%s\n' "$*" >> "${REFRESH_DASHBOARD_STUB_ARGUMENTS_FILE}"

OUTPUT_FILE=""
while [ $# -gt 0 ]; do
  case "$1" in
    --output)
      OUTPUT_FILE="$2"
      shift 2
      ;;
    --pr-data)
      cp "$2" "${REFRESH_DASHBOARD_STUB_PULL_REQUEST_DATA_COPY}"
      shift 2
      ;;
    *)
      shift
      ;;
  esac
done

printf '<html>stub dashboard</html>' > "${OUTPUT_FILE}"
printf '%s\n' '{"corrected": [], "counts": {"not_started": 1, "in_progress": 0, "blocked": 0, "deferred": 0, "done": 2}}'
