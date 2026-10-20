# basstler-package

- Everything else about basstler, its items and its standing rules, lives in AbdelrhmanBassiouny/basstler's notes: its `claude/personal-notes` branch, `.claude/personal/plans/basstler-package/`.

## cram-basstler-removal (#523)

- One pull request off fork main, carrying both halves basstler's own plan splits in two (cram-uses-basstler-plugin, cram-basstler-removal): this plan tracks them as one item.
- Adds `.claude/basstler/stack.toml` (upstream cram2), plugin enablement in `.claude/settings.json`, and `upstream-reviews.yml` as a caller of basstler's reusable workflow at v0.1.5.
- Deletes basstler/, test/basstler_test/, .claude/hooks, the plugin's skills, .claude/stack, .claude/SETUP.md and the test_basstler CI job. `local-code-review` stays: it is CRAM's own, not the plugin's. `scripts/sync_version.py` discovers packages by glob, so it needs no edit.
- AGENTS.md's PathEnumeration rule names basstler's class; it is reworded to state the overrides instead.
- Fork labels move from cram2-link-sent to promotion-link-sent. Promotion to cram2 waits for the user's OK.
