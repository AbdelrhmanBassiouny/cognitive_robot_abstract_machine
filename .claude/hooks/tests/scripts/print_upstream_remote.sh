#!/bin/bash
# Calls current_branch_upstream_remote the way create-personal-notes-branch.sh does:
# assigned at top level under `set -euo pipefail`, where a non-zero status aborts the
# whole script rather than reading as "there is no upstream".
#
# Usage: print_upstream_remote.sh <path to resolve-personal-notes-config.sh>
set -euo pipefail

source "$1"

upstream="$(current_branch_upstream_remote)"
printf 'upstream=[%s]\n' "${upstream}"
