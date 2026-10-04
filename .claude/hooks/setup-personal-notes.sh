#!/bin/bash
set -euo pipefail

# The whole one-time personal-notes setup, non-interactively. A shim: the setup
# itself is basstler/setup_personal_notes.py, whose docstring is the usage, and
# this path is kept so the setup skill and the hooks README name one command.
#
#   ./.claude/hooks/setup-personal-notes.sh --remote <name-or-url> \
#     [--name "Your Name" --email you@example.com] [--starter-notes] [--create-labels]

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/resolve-personal-notes-config.sh"
exec python3 -m "${SETUP_PERSONAL_NOTES_MODULE}" "$@"
