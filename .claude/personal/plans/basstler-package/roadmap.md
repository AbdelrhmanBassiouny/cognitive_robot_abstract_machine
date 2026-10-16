# basstler-package — standing rules

- Tooling freeze until cram-basstler-removal opens: no new pull request touches basstler/, test/basstler_test/, .claude/ tooling or the tooling workflows in CRAM. New tooling work starts in AbdelrhmanBassiouny/basstler once it exists.
- The conversion items follow the carried-over bash-touching pull requests, not lead them: a wholesale body rewrite conflicts with every carried branch.
- Two carriers are unreachable from the migration branch and stay with `basstler-github-api-unification`, whose two remaining carriers live on other plans' branches.

## basstler-plugin-spike (#516, never merges)

- Probe plugin `basstler-spike` (one skill, one SessionStart hook) lives on the spike branch under `basstler-plugin-spike/`; `.claude/settings.json` registers that marketplace (github source, `path` into the branch) and enables the plugin, whose own source is `git-subdir` pinned by `sha`.
- Run: a fresh cloud session started on the spike branch reports whether the skill is listed, whether the hook's context line and marker file appear, and what `CLAUDE_PLUGIN_ROOT`/`CLAUDE_PROJECT_DIR` were.
- The spike repository is the fork, not `AbdelrhmanBassiouny/basstler` (which does not exist yet), so access to a second repository from a session is not exercised.

## basstler-repository-extraction

- The new repository is public (user's call, 2026-10-16): the plugin marketplace and the hook's `pip install git+…@v0.1.0` need no credentials that way. The GitHub App cannot create repositories (403), so the user creates it empty and installs the App; the session pushes.
- History: `git filter-repo` over a mirror of #501's tip (becomes `main`) and every open tooling branch in the carryover list, plus the bases they stack on. Kept and renamed: `basstler/`→root, `test/basstler_test/`→`tests/`, `.claude/skills|hooks|shared|upstream_reviews`→`plugin/…`, `.claude/stack`→`docs/stack`, `.claude/SETUP.md`→`docs/SETUP.md`, tooling workflows (`upstream-reviews`, `stack-maintenance`, `tooling-label`, `integration-*`) unchanged. The misspelled `bastler/`/`test/bastler_test/` era stays unrenamed (only stale branches reach it; renaming collides at merges). Not carried: `.claude/settings.json`, `claude_reviews`, `.github/actions_budget.py` (CRAM-side), the spike branch, #515.
- The standalone commit lands as a draft pull request in the new repository from `claude/jolly-gauss-l2pjrh`, so the rewritten history and the new-repo changes review separately; `v0.1.0` is tagged on its merge.
