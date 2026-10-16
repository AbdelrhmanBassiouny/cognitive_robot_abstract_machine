# basstler-package — standing rules

- Tooling freeze until cram-basstler-removal opens: no new pull request touches basstler/, test/basstler_test/, .claude/ tooling or the tooling workflows in CRAM. New tooling work starts in AbdelrhmanBassiouny/basstler once it exists.
- The conversion items follow the carried-over bash-touching pull requests, not lead them: a wholesale body rewrite conflicts with every carried branch.
- Two carriers are unreachable from the migration branch and stay with `basstler-github-api-unification`, whose two remaining carriers live on other plans' branches.

## basstler-plugin-spike (#516, never merges)

- Probe plugin `basstler-spike` (one skill, one SessionStart hook) lives on the spike branch under `basstler-plugin-spike/`; `.claude/settings.json` registers that marketplace (github source, `path` into the branch) and enables the plugin, whose own source is `git-subdir` pinned by `sha`.
- Run: a fresh cloud session started on the spike branch reports whether the skill is listed, whether the hook's context line and marker file appear, and what `CLAUDE_PLUGIN_ROOT`/`CLAUDE_PROJECT_DIR` were.
- The spike repository is the fork, not `AbdelrhmanBassiouny/basstler` (which does not exist yet), so access to a second repository from a session is not exercised.
