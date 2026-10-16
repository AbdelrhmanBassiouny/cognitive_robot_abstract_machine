Item basstler-package/basstler-repository-extraction. Work for AbdelrhmanBassiouny/basstler; standalone branch backed up on the fork as claude/jolly-gauss-l2pjrh (basstler history, not CRAM).

Plan
- Push filtered history: main = #501 tip; rewritten tooling branches (re-run filter-repo per roadmap section if the scratch mirror is gone).
- Push claude/jolly-gauss-l2pjrh to the new repo, open its draft PR against main. Tag v0.1.0 on merge.
- Then push claude/validate-manifest-before-save (local only, stacked on it): bug PR, save-plan.sh validates via plan_manifest_tools validate.

Done
- 5 commits on main (plugin split, project stack.toml, workflows+CI, .claude on demand, generic names + docformatter). 752 pass.
- Notes branch 0f6ab95e2: statuses respelled with underscores (readable by old and new dashboards). Dashboard republished (v9).

Next
- Blocked: Claude GitHub App not installed on AbdelrhmanBassiouny/basstler (pushes 403).
