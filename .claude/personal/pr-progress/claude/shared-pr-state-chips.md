# PR 3: shared pr_state module + LOC/CI/conflict chips (plan-dashboards / shared-pr-state-chips)

Branch `claude/shared-pr-state-chips`, PR #111 (draft). Kickoff session:
https://claude.ai/code/session_014KoJeaTUxyECZZpfWiVmvr. Resolve session (2026-09-02):
https://claude.ai/code/session_01VATBfAq9Rd7jdU46rw3hvd.

## History (condensed)

- 2026-07-30: created the `development_tooling` package with `pr_state` + `personal_notes`,
  restored `stack.py export`, added CI/LOC/conflict chips to dashboard items, added
  `build_site.py` (headless static build), 44 package tests + 258 tooling tests. Stacked on #106.
- 2026-08-05: #106 landed; resolved the first main conflict by re-applying deltas in main's idiom.
- 2026-08-20: bastler pivot (decision 13): #185 creates the package off main; this PR rebases onto
  it and folds its modules in under the `bastler` name. Left needs-resolution since (3 files vs main).
- 2026-08-30: owner review, 19 threads (2 "rebase onto bastler", 17 code-quality). Never recorded
  in the manifest until the resolve run.

## Resolution plan (2026-09-02, auto mode)

1. Merge `origin/claude/plan-item-kickoff-workflow-cuare2` (#185 head) into this branch - a merge,
   not a rewrite; #185 already contains this branch's last main merge, so no stray main commits
   enter the diff. Resolve: delete the two per-directory test conftests; take bastler's README /
   ci.yml / build_dashboard.py / stack.py and re-apply this PR's deltas as `bastler.pr_state`
   imports (no sys.path inserts); move the four location-conflicted test files into
   `test/bastler_test/`.
2. Fold: `development_tooling/pr_state.py` -> `bastler/pr_state.py`, `personal_notes.py` ->
   `bastler/personal_notes.py`, `build_site.py` -> `bastler/build_site.py`; tests + stubs into
   `test/bastler_test/` (gh stub merged into the shared `gh.sh`); delete `development_tooling/`,
   `test/development_tooling_test/`, the second CI invocation and the `DEVELOPMENT_TOOLING_*` shell
   constants (`BUILD_SITE_MODULE` replaces `BUILD_SITE_SCRIPT`).
3. Apply the 17 code-quality threads while re-homing: loose functions grouped into classes
   (check rollup, session link, change size, fetcher, local git probe, endpoint paths);
   StrEnums for payload keys / list filter / check display / mergeable display / environment
   variables; module constants as ClassVars; member docstrings; test data files under
   `dataset/`; ScratchRepository instead of hand-rolled git; fakes as dataclasses; a session-link
   factory for tests.
4. Verify: `python -m pytest test/bastler_test --confcutdir=test/bastler_test`, format_docstrings,
   every entry point answers `--help`. Push; retarget #111 to `claude/plan-item-kickoff-workflow-cuare2`;
   update the description; reply on and resolve each addressed thread; keep draft.
5. Record: roadmap addendum, manifest blockers trimmed, dashboard republished.

Deferred, stated on the PR: the stack chip (REST read of the pull request's native stack object)
is still specified-not-implemented; it is the item's remaining feature work after this round.

## Done so far

- Context gathered; manifest corrected (status in_progress, session, 3 precise blockers, notes).

## Next

- Steps 1-5 above, in order.
