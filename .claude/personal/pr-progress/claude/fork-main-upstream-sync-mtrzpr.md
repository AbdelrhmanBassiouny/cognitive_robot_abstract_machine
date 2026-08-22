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

## Next

Nothing outstanding. Dashboard republished (same URL), structural change recorded on
tracking issue #102. PR #188 is open as a draft with the `bug` label; per my notes,
opening it ends this session's obligation to it.
