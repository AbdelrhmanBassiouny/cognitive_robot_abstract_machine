# PR #123 — ready-for-review ends a session's job

Personal-notes-only change: `.claude/personal/cram-notes.md`, PR based on and
targeting `claude/personal-notes`. No plan item (never reaches `main`, no code),
no manifest edit, no dashboard republish.

## Plan

1. Generalise `## When your branch merges or closes` → `## When your PR's job
   ends`, covering merged / closed / user-marked-ready with the one existing
   teardown checklist rather than a second copy. — done
2. Widen the teardown from "subscriptions held solely for that branch's sake" to
   everything subscribed on the finished PR's behalf (tracking issue, dependency
   or parent PR, upstream mirror), plus: if it was the session's only work, the
   turn ends with nothing subscribed and nothing armed. — done
3. Two carve-outs in `## Pull requests` so it no longer contradicts the above
   (always-re-draft, always-subscribe). — done
4. Commit as the user, push, open as draft with the session link, subscribe. — done

## Decisions settled with the user

- Only a draft→ready flip **the user made** is terminal. A session marking its own
  PR ready — on instruction, or self-undrafting to unblock dependents as on #106 —
  is not the signal and keeps working.
- On the signal: report loose ends (red CI, conflict, unresolved thread) in the
  chat, then tear down anyway. Do not stay to fix them.
- Scope is personal notes only — `main`'s `starter-notes.md` and the plan skills
  stay untouched.
- No plan item, per the user's revision to the approved plan.

## State

Draft PR #123 open, still 1 file, +30/−10 — verified after the restack below.

Restacked by another session on 2026-08-02 18:11: it merged `origin/claude/personal-notes`
into this branch ("Merge remote-tracking branch ... into
restack-claude/pr-review-completion-rules-nznmmf"), taking the head from `afcbf1e4`
to `b21c693a`. Merged cleanly; this PR's own diff is unchanged, so the description
still matches and needs no edit. The base gained an unrelated `cram-notes.md`
section ("New PR/item, or a change to one already in flight?") that does not touch
either section this PR edits.

CI is red and stays red. `claude/personal-notes` carries a stale snapshot of the
source tree — merge-base with `main` is `9703a398`, and 1199 files differ — so the
full robotics matrix runs against months-old source. Both workflows were green on
`main` at `82501888` and fail here. Two distinct failures so far, neither reachable
from a markdown-only diff:

- `Examples and Demos` → `test_each_lib (coraplex/demos/coraplex_real_tracy/test_demo.py)`:
  `semantic_digital_twin` circular imports.
- `CI` → `test_each_lib (semantic_digital_twin)`: 813 passed, 2 errors.
  `test_apartment_semantic_annotations` and `test_explain_inferred_semantic_annotations`
  raise `BrokenWorldModificationHistoryError` ("world entity not in the kwargs of
  the method that created it"). Both the implicated `world.py` (+253/−154 vs `main`)
  and that test file are stale on this branch, which is the cause.

Both failures recurred identically on the post-restack head `b21c693a`:
`semantic_digital_twin` (run 30760569205 — same two tests, 813 passed / 2 errors,
only the random entity UUID differing) and the `coraplex_real_tracy` demo
(run 30760569189 — same `semantic_digital_twin.world` circular imports, exit 1).
Restacking onto a newer notes-branch tip does not help, because the notes branch
itself is what lags `main`. Both recurred again on `56a6e1b4` after a second
restack on 2026-08-03; no source file differs between those two heads, only
`.claude/` data. Treat any further failure on this PR as this same cause unless
the job name is one not yet seen.

Trap when checking that: these restacks keep moving the base, so a three-dot
`git diff origin/claude/personal-notes...<branch>` against an unfetched base ref
shows the base's own commits as if this PR added them — it read as 7 files once.
Fetch the base first, or just trust the API's `changed_files`, which stays at 1.

Inherent to every PR targeting this branch, not to this one. Not chased, and
deliberately not "fixed" by merging `main` into the notes branch — that would be a
large unrelated change to the user's branch, and is the user's call.

## Environment note for a future session

`.claude/hooks/` does not exist on `claude/personal-notes`, so checking a PR branch
based on it out in the primary worktree deletes the tooling that saves this file.
Work in a second worktree, and move the primary worktree's HEAD with
`git symbolic-ref` (files untouched) only for as long as `save-pr-progress.sh`
needs a branch name to key on.

## Next

Nothing. Awaiting the user's review. Per this PR's own rule, converting it out of
draft ends this session's job on it: unsubscribe from #123 and stop.
