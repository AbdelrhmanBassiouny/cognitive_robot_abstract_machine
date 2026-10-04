#!/bin/bash
# Prints the labels resolve-personal-notes-config.sh declares, one per line, so a test
# can hold its own enum against the shell's declaration instead of a copy of it.
#
# Usage: print_pull_request_labels.sh <path to resolve-personal-notes-config.sh>
set -euo pipefail

source "$1"

printf '%s\n' "${PULL_REQUEST_LABELS[@]}"
