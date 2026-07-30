# PR 3: shared pr_state module + LOC/CI/conflict chips (workflow-unification / shared-pr-state-chips)

Branch `claude/shared-pr-state-chips`, based on `claude/stack-tooling-on-main` (#106's head,
sibling of #107). Kickoff session: https://claude.ai/code/session_014KoJeaTUxyECZZpfWiVmvr
Approved kickoff plan (decisions settled with the user: package named `development_tooling`;
headless site build also pushes merged→done manifest corrections).

## Plan

1. `development_tooling/` package at repo root (zero-install import; pyproject inside the
   directory for optional install) with `pr_state` as first module — compute layer ported from
   old `dev/stack.py` (CI rollup reduction, session-URL parse, LOC-vs-threshold; no stack-turn).
2. Fetch layer: gh-else-token dual backend (decision 9), bulk list + per-PR GETs for
   additions/deletions/mergeable; git-based `_loc_changed`/`_conflicts_onto` ports.
3. `.claude/stack/stack.py` regains `export`, backed by the package (repo-root sys.path insert,
   interim until dev-tooling-python-package).
4. Dashboard chips: optional pr_data fields (ci/additions/deletions/mergeable/session_url),
   `PullRequestRecord` defaults keep old pr_data working, chips in `.item-badges`.
5. Headless `build_site.py` in the plan-dashboard skill dir: discovers plans from personal-notes,
   fetches via pr_state, runs refresh_dashboard.sh per plan (incl. correction push), build_index;
   writes `_site/`.
6. Tests TDD throughout: `test/development_tooling_test/` + stack tests + plan-dashboard tests
   (backward-compat, ScratchRepository for build_site). CI: new constants + add test dir to
   test_claude_dev_tooling job.

## Done so far

- Kickoff research + approved plan; branch created; plan.yaml set to in_progress and saved;
  dashboard republished.

## Next

- Step 1: failing tests for pr_state compute layer, then the package skeleton + module.
