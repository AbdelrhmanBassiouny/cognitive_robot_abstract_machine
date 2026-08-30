# PR #110 — /setup-stacked-prs, its setup script and read-only checker

Item `setup-stacked-prs-skill` of plan `stack-tooling-install` (tracking issue #102).
Base: `claude/setup-personal-notes-script` (#107). Draft, and staying a draft.

## What this session was for

`/plan-item-resolve stack-tooling-install setup-stacked-prs-skill`, in `auto` mode.
Found the item stalled on two things at once, neither recorded in the manifest: the
pull request was `dirty` against its base, and the pending review the previous session
could not reply into had been submitted, turning two invisible threads into 27 with a
25-thread round dated the same day.

## Done

- Merged the base (`b2e62ae2`). Five files conflicted; `setup_report.py` was an add/add
  keeping both sides, and the other four were one duplicated mechanism, resolved in
  favour of the base's `HookScript`-typed shape with this branch's constant-resolution
  folded in.
- Applied the whole round (`81285492`, `485ceda5`) and generalized it past the files
  commented on, as asked.
- Replied to all 27 threads; resolved 25.
- Updated the pull request description and the plan manifest/roadmap.

## Left open on purpose

Two threads, both answered differently from what they asked, both about `GitCommandRunner`:
whether it should serve callers under `.claude/hooks/tests/` (needs a production `sys.path`
insert — `bastler-notes-core-python`'s seam), and whether the `git remote add` line
`stack.py` prints for a person to paste should come from a command factory when nothing
runs it. Neither is resolvable inside this pull request; both are the user's call.

## Next

Nothing from this session. 638 tests pass locally across the four directories CI runs, and
the five previously-inherited failures are gone. Awaiting review; the branch stays parented
on #107 until `github-api.sh` reaches `main`.
