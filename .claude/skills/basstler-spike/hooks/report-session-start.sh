#!/bin/bash
# Records that this plugin's SessionStart hook ran, and in which environment, both
# in a marker file and in the session's context.
set -euo pipefail

marker_directory=/tmp/basstler-plugin-spike
mkdir -p "${marker_directory}"
report="basstler-plugin-spike: session-start hook ran (skills-dir copy) at $(date -u +%Y-%m-%dT%H:%M:%SZ)
CLAUDE_PLUGIN_ROOT=${CLAUDE_PLUGIN_ROOT:-unset}
CLAUDE_PROJECT_DIR=${CLAUDE_PROJECT_DIR:-unset}
CLAUDE_CODE_REMOTE=${CLAUDE_CODE_REMOTE:-unset}
working directory=$(pwd)
python3=$(python3 --version 2>&1 || echo missing)"
echo "${report}" >> "${marker_directory}/session-start.txt"
echo "${report}"
