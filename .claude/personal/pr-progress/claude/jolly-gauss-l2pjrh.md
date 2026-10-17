Item basstler-package/basstler-repository-extraction: draft PR AbdelrhmanBassiouny/basstler#1 (branch claude/jolly-gauss-l2pjrh there); bug fix basstler#2 stacked on it.

Plan
- Review and merge basstler#1; its green run on main tags v0.1.0 itself (release job). Version lives only in plugin.json (hatchling, d36e1de22). basstler#2 then retargets to main.

Done
- basstler main = #501 tip filtered, plus the 24 rewritten tooling branches; #1 and #2 open as drafts. 752 / 755 tests pass.
- Notes branch: statuses with underscores; cram-notes.md renamed to notes.md (a31b24f99). Dashboard v10.

Next
- User: set CLAUDE_PERSONAL_NOTES_PATH=.claude/personal/notes.md in the cloud environment (CRAM tooling still defaults to cram-notes.md).
- CI on basstler#1 not yet checked.
