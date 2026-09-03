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

- Context gathered; manifest corrected (status in_progress, session, precise blockers, notes);
  dashboard republished.
- Steps 1-4 done 2026-09-02: merge commit 23f54b22 (fold + review round) and d6b8035a (two
  docstrings the formatter split) pushed; PR #111 base -> `claude/plan-item-kickoff-workflow-cuare2`,
  description rewritten, still draft; 17 threads replied to and resolved, 2 replied to and left
  open on purpose (GitCommandRunner-in-tests answered with ScratchRepository; the "discuss the
  rebase options" thread carries the three options and the choice). 698 bastler tests pass;
  format_docstrings converges on every new file.
- Formatter finding: docformatter expands one-line member docstrings and eats the blank line
  after the last member of a class, so a new file converges only when its member docstrings are
  already three-line. stack.py and build_dashboard.py were already declined on #185's head.
- Step 5: manifest blockers/notes updated; dashboard republished.
- 2026-09-03: CI on d6b8035a was red, but stale: the run's merge commit was head + main (it started
  before the base retarget, and `pull_request` has no `edited` type to re-run on a base change).
  `test_bastler` tripped on main's `.claude/hooks/setup_steps.py` + its test, which is #185's own
  needs-resolution conflict; the suite passes on the true merge ref (698). The giskardpy failure is
  a robotics test this branch never touches, green on #185 and main. Explained in one PR comment;
  nothing pushed to kick CI. It re-runs against the retargeted base on the next real push.

## Next

- Nothing until the user answers the two open threads or #185 lands (the routine restacks this
  branch on #185 from now on; GitHub retargets the base to main when #185 merges).
- Remaining feature work for this item, not started: the stack chip (REST read of the native
  stack object with the 2026-03-10 API version header).
