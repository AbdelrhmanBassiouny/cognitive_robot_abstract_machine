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

- 2026-08-05: #106's chain landed on main, GitHub retargeted #111 to main, and the
  maintenance pass reported a real conflict (needs-resolution) in stack.py, README.md,
  build_dashboard.py. Resolved by taking main's re-reviewed versions and re-applying
  this PR's deltas in their idiom (export as a Command member via
  Configuration.fork_repository, own URL helper deleted in favour of
  Repository.from_remote_url, ExitCode.GITHUB_UNAVAILABLE 6, personal-notes resolver
  delegation kept, from_mapping keeps #119's guard + chip fields). 401 tests green
  (357 .claude suites + 44 development_tooling); pushed merge 52e3ede4; replied on the
  PR; label clears on the next maintenance pass.
- Watch CI on the merge commit; the known test_world_sim_state_sync flake may still red
  the semantic_digital_twin job (fails on main too - already noted once on the thread).
- 2026-08-05 (later): the pass merged main again (2b316dc5, clean - #492 gripper
  params); run 31044969651's robokudo job red on infrastructure only (uni GitLab
  unreachable while downloading test data; noted on the thread). rerun_failed_jobs was
  refused while the run's other jobs still execute - retry it on the next event for
  this run once it has completed.
- Keep the PR draft until told otherwise; self-review pass before undrafting, when asked.
