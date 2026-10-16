Item basstler-package/basstler-repository-extraction. Work lives in AbdelrhmanBassiouny/basstler, branch claude/jolly-gauss-l2pjrh (prepared locally; repo not created yet).

Plan
- Filtered history (#501 tip as main + open tooling branches) pushed to the new repo.
- Standalone commit as draft PR: own CI, plugin manifest + marketplace, consumer stack.toml, one venv location, reusable workflows, hook installs from git tag. Tag v0.1.0 on merge.

Done
- Mirror filtered with git filter-repo (paths in roadmap section); secret scan clean.

Next
- User: create empty public repo, install Claude App. Then add_repo push, push mirror, open draft PR.
- Make the suite pass in the new layout, then the standalone changes, TDD.
