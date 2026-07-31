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

- Kickoff research + approved plan; branch created; plan.yaml kept current throughout;
  dashboard republished (now itself showing the new CI/LOC/conflict chips, fetched live
  through the new pr_state module).
- All six steps implemented TDD, 5 commits, pushed; **draft PR #111 opened** (base
  claude/stack-tooling-on-main), subscribed to its activity. 302 tests green across the
  two CI invocations (was 254): plan-dashboard+hooks+stack (258) and
  test/development_tooling_test (44, separate invocation with --confcutdir because
  test/conftest.py imports the robotics stack).
- Notable findings while porting: merge-tree exits 1 for both a conflict and a missing
  reference (old probe reported a typo as a conflict - fixed with explicit rev-parse
  verification); a test fetched the real personal-notes remote via the session's
  CLAUDE_PERSONAL_NOTES_REMOTE env leak - both personal_notes and build_site test
  modules now strip those vars via an autouse fixture.
- Verified contracts: zero-install import from repo root, stack.py CLI (export listed),
  `pip install ./development_tooling` (package-dir mapping works), and a live pr_state
  fetch of PRs 101/106/107/109/110/111 (chips data correct).

## Next

- CI on #111 (head 8cb9fef1, after the stack Routine restacked the chain main -> #101 ->
  #106 -> this branch with merge commits; local branch fast-forwarded to match): every
  job green - test_claude_dev_tooling and coraplex included - except the one known
  pre-existing test_world_sim_state_sync failure, identical assertion on both runs and
  on main (noted once on the PR thread; no re-noting per event). Re-check when the base
  recovers.
- Keep the PR draft until told otherwise; self-review pass before undrafting, when asked.
