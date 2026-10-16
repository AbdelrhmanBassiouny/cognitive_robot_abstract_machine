basstler-plugin-spike, draft #516 (never merges), base main.

Plan:
- Probe plugin under basstler-plugin-spike/ (skill + SessionStart hook), plugin source git-subdir pinned by sha.
- .claude/settings.json: extraKnownMarketplaces (github, path into this branch) + enabledPlugins.
- Child cloud session on this branch reports skill/hook/env; record pass or fail.

Done:
- Branch re-cut from main, #516 opened, manifest and roadmap recorded.

Next:
- Add plugin, validate with `claude plugin validate`, pin sha in settings, push, run child session.
