## Plan

Item `session-branch-base` of plan `workflow-unification` (track `stack-tooling`), PR #199,
draft, based on `main`, labelled `bug`. Reasoning in `roadmap.md` under the kickoff entry and
the 2026-08-28 reversal.

**The default branch stays `integration`.** It is the fast-PR process - it puts
reviewed-but-unlanded work into every fresh checkout - and the kickoff's recommendation to flip
it back was wrong. The requirement is that a pull request be based on `main` or a parent pull
request, never on `integration`; where a clone starts and where a branch is cut from are
separate events, and only the second can be a defect.

## Done

- `configured_base_branch()` / `repository_default_branch()` in
  `resolve-personal-notes-config.sh`; `default_branch_name()` prefers the configured base, which
  is what stops `pr_progress_path` and `branch_can_hold_plan_item` treating `integration` as the
  branch no plan item can track.
- `check-setup.sh` `branch_base` row: refuses a branch that **descends from** the staging default
  (`git merge-base --is-ancestor origin/integration HEAD`). Ancestry against the staging branch,
  never against `main` - `main` moves, so testing against it flags every branch that has not
  merged it recently and cannot tell a branch cut from `integration` from one stacked on a parent.
  0 of this fork's 198 remote branches are flagged.
- Verified both directions live: `ok` on this branch, `needs-setup` naming the remedy in a
  worktree cut from `integration`'s tip.
- 541 tests across the four CI directories, from 538. The mutation testing ancestry against the
  configured base fails exactly the test written to reject it.
- Repaired two truncated `plan.yaml` notes (unquoted scalars containing ` #<number>`):
  `session-branch-base` 407 of 1881 chars, `unfetched-parent-branches` 51 of 2641. Swept the
  manifest; nothing else affected.

## Next

- Nothing blocking. The PR is a draft; no default-branch change is needed or wanted.

## Open, for the developer

- **`integration` is 124 commits / 5 days behind `main`** (built 2026-08-23, `main` tip
  2026-08-27), so the fast-PR process is serving unlanded work on a stale base. #188 freshens
  `main` while the session sits on `integration`, so the working tree never sees it. The fix is
  rebuilding integration, not fast-forwarding main and not the maintenance pass - but
  `integration.py build` is only on #154, so a fresh clone cannot run it. Scheduled rebuild vs.
  landing #154 is their call.

## Watch

- Textual overlap with #188 (`resolve-personal-notes-config.sh`, `session-start.sh`'s test module)
  and #185 (the first). Both open, both on `main`; whichever lands second merges.
- No PR-activity subscription and no scheduled check-ins, per personal notes. The tracking-issue
  subscription was refused by the permission classifier, so this session is not on that channel.
