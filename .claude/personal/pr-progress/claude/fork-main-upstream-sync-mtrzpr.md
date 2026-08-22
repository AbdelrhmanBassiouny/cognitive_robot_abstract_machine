## Plan

Make every session start from a fresh base: a deterministic SessionStart step that
fast-forwards the fork's default branch from the upstream repository, locally and on
the fork, and reports how stale the checked-out branch is.

Tracked as `workflow-unification` item `fresh-base-at-session-start` (personal-data
track). PR #188, draft, `bug` label.

Design decisions (all implemented):
- `.claude/hooks/fast-forward-default-branch.sh`, run as a subprocess by
  session-start.sh, printing its outcome plus indented follow-up rows.
- Upstream resolved from `stack.py configuration`, so no repository is named in the
  hook and there is one place to correct if the upstream moves.
- Fast-forward only, never a force push; a diverged base is reported and left alone.
- Only the default branch is touched; the checked-out branch's staleness is reported,
  never merged or rebased automatically.
- Never fatal: every refusal reports and exits 0.

## Done

- Hook, wording in session-start-messages.sh, `default branch` line in the report.
- 19 tests in `.claude/hooks/tests/test_default_branch_fast_forward.py`, no network:
  fork and upstream are local bare repos laid out under `<owner>/<name>.git` so their
  URLs name a repository the way GitHub does; the GitHub-URL route is reached through
  git's own URL rewriting. No test-only seam in the script.
- Mutation-checked: disabling the push fails 4 tests; dropping the divergence guard
  fails the diverged test.
- Second fix, same root cause: the summary's `plan state SHA` was re-reading
  FETCH_HEAD, which the upstream fetch clobbers. Now prints the recorded stamp.
  Reproduced with a failing test first.
- Verified live: origin/main was 86 commits behind cram2/main, fast-forwarded in 3.9s.
- Merged the fresh main into this branch. Full suites green (280 hooks+stack, 497
  including plan-dashboard).
- Plan item and roadmap entry saved to the notes branch.

## Review round 2026-08-22 (b0e28437)

Three threads, all one finding: the tests hand-rolled git where GitCommandRunner
already exists on main, and the harness holding them together was a plain class.

- The fork layout moved out of `scratch_repository.py` into a new
  `forked_scratch_repository.py`. That leaves the shared harness every other hook
  test builds on byte-identical to main, and gives the fork-specific setup a home
  that can use the runner. Using it for my new methods alone would have left two
  conventions in one class; converting `ScratchRepository` wholesale is 66 call
  sites across seven modules and belongs to the bastler migration.
- `ForkedScratchRepository` and `GitHubRepositoryStandIn` are frozen dataclasses
  built by a `laid_out_in` classmethod - the `ToolingCheckout` shape from #158.
- Every git call goes through `GitCommandRunner`; the push is a `ProposedPush`;
  `branch_tip` no longer shells out. One call stays spelled out with a comment:
  creating the default branch on an unborn HEAD, where `checkout -B main HEAD`
  fails because there is no commit for a starting point to name.
- Reached by adding `.claude/stack` to the hooks conftest path. No new coupling:
  the hook under test already resolves its upstream through that directory, and
  `.claude/stack/tests/conftest.py` already adds the hooks directory the other way.

Re-verified: 19 tests here, 280 across hooks+stack, and the mutation check still
bites (disabling the fork push fails the same 4). All three threads replied to and
resolved; PR description updated; still a draft.

## Next

Nothing outstanding. Dashboard republished (same URL), structural change recorded on
tracking issue #102. PR #188 is open as a draft with the `bug` label; per my notes,
opening it ends this session's obligation to it.
