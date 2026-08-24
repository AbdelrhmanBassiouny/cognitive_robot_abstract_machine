## Why PR #64 was never reparented/promoted - stack tooling investigation

**Root cause (proven, not inferred).** `stack.py`'s `fetch()` fetches only the
*head* branches of the open pull requests on the board
(`fetch(configuration, [pr.head for pr in prs])`, stack.py:930/941-948). A parent
branch whose own pull request is closed or merged is not on the board, so its
`origin/<parent>` ref is never fetched. `_merged_predicate.is_merged` then runs
`git merge-base --is-ancestor origin/<parent> cram2/main` through `_git_succeeds`,
which cannot tell exit 128 (ref missing) from exit 1 (not an ancestor) - so a
missing ref reads as "parent has not landed". That silently suppresses the
reparent, the promotion, and turns the restack into `merge: origin/<parent> - not
something we can merge`.

Demonstrated in this checkout: with `origin/D-core-aid` present,
`stack.py reparents` prints `D-core-underspecified 64 D-core-aid main` and
`stack.py next` lists #64 as promotable; after `git update-ref -d
refs/remotes/origin/D-core-aid` both go silent.

**Not the cause:** the fork's default branch being `integration`. cram2's default
is still `main` and `upstream_base` is pinned in `.claude/stack/stack.toml`, so the
tooling never reads a default branch. (Separate latent hazard: `origin/HEAD` now
points at `integration`, which is what `default_branch_name` in
`resolve-personal-notes-config.sh` reads, and what a UI-opened PR would default its
base to.)

**Secondary defects found in the same area**
1. `_git` swallows a failed `git fetch` entirely; and `git fetch <remote> a b c`
   is all-or-nothing, so a single deleted board head aborts the whole fetch and the
   pass then computes on stale refs, silently.
2. `reparents` only ever retargets onto `upstream_base`. #178's parent
   (`montessori_live_event_timeline_tab`, PR #175) merged into its *grandparent*
   `montessori_fast_inline_monitor`, not upstream - no rule covers that.
3. #79 and #21 have parents whose PRs were closed *without* merging (#78, #20).
   `reparents`' docstring claims it covers a closed-not-merged parent; it only
   covers a closed-but-landed one.

**Status:** investigation complete, findings presented to the developer. No code
written yet.

**Next:** agree the fix shape before implementing. Proposed:
(a) fetch the bases as well as the heads; (b) make a missing ref an explicit error
rather than a False answer; (c) make a failed fetch loud; (d) decide the policy for
a parent whose PR is gone (closed unmerged, or merged into a non-upstream branch).
Each needs a failing test in `.claude/stack/tests/` first - `fetch()` has no test
coverage at all today.
