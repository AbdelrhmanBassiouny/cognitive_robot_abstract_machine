# Bash→Python refactor study (claude/bash-python-refactor-study-fvf67e)

Study session, 2026-08-01: assessed converting the .claude/ bash tooling to Python.
No code changes on this branch; no PR. The deliverable was the study + registering
the work in the workflow-unification plan (decision 12).

## Done
- Full study: hooks inventory, skills/script contracts, duplication + defect list,
  workflow-unification placement, krrood-dependency verification (all in the
  roadmap's decision-12 update and the #102 comment of 2026-08-01).
- Registered 8 new items in workflow-unification (dashboards track):
  dev-tooling-notes-core-python → save-commands → save-plan / session-start /
  setup-checks / dashboard-refresh → config-shim-slimming, plus
  dev-tooling-github-api-unification. Manifest+roadmap saved (e2723f7d),
  #102 commented, dashboard republished (33 items, drift 0).
- Decisions (user): 7 staged items; python3>=3.11 hook floor with inert-skip shim
  accepted; v1 fully krrood-independent — future dev-tooling-krrood-adoption plan
  once krrood APIs (dag-facade-hardening, eql-performatives, eql-verbalization)
  and the converted tooling stabilize; EQL/verbalization are tier-3 feature work
  for that future plan only, never in conversion items.

## Next
- Nothing further on this branch. Conversion work starts from the plan items,
  sequenced after in-flight bash-touching PRs (#107 #109 #110 #115 #121 #126)
  and dev-tooling-python-package; kick off dev-tooling-notes-core-python first
  via /plan-item-kickoff when its dependencies are ready.
