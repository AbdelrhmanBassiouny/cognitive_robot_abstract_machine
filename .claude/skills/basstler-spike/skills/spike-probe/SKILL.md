---
name: spike-probe
description: Report that the basstler-spike plugin's skill was loaded. Use only when asked to run the basstler plugin spike probe.
---

# Spike probe

Reply with the line `basstler-plugin-spike: skill loaded`, followed by the
output of `ls "${CLAUDE_PLUGIN_ROOT}"` and the contents of
`/tmp/basstler-plugin-spike/session-start.txt` if that file exists.
