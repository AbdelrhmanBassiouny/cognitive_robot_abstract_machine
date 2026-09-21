# resolve-propagates-downstream (PR #430, plan `plan-tracking-skills`)

Branch `claude/plan-item-kickoff-resolve-ic3qnu`, based on #185
(`claude/plan-item-kickoff-workflow-cuare2`) because the new code is Python and
#185 is where the `.claude/` modules live in `basstler/`.

## Plan

1. `branches_stacked_on(stack, branch)` in `basstler/stack.py` - the not-yet-merged
   branches whose parent chain reaches the named one, parent before child. Walks
   `Branch.parent`, not git containment (reasons in the roadmap section).
2. `restack_plan(stack, stacked_on=None)` and `restack(..., stacked_on=None)` - the
   existing `RESTACK_STEPS` restricted to that subtree, no second propagation path.
3. A conflict response chosen by the same argument: `TellTheBranchOwner` (label +
   comment, today's behaviour) for a whole-board pass, `LeaveItToTheCaller` (the
   outcome and its conflicting paths, nothing written to GitHub) for a named subtree.
4. `maintenance restack --stacked-on <branch>` as the session-facing entry point.
5. `.claude/skills/plan-item-resolve/propagating-a-fix.md` - the parent-to-descendant
   judgement - referenced by one line from that skill's `SKILL.md` (contended file).

Tests first throughout, in `test/basstler_test/test_stack.py` and
`test_maintenance.py`, plus one guarding the skill's reference to the new document.
Suite: `python -m pytest test/basstler_test --confcutdir=test/basstler_test`.

## Done

- Branch cut from #185's head, draft PR #430 opened, manifest and roadmap written.
- All five steps implemented and pushed as one commit; PR description rewritten to match.
  679 tests pass (664 on the base), `python3 -m pytest test/basstler_test --confcutdir=test/basstler_test`.

## Review rounds

- **2026-09-21, two threads on `test_stack.py`** (retyped branch names): answered and
  resolved, fixed in `8fbbf4ede`. `StackBranch` in `test/basstler_test/constants.py`,
  shared by both suites; `a_three_deep_stack()` builds the stack suite's fixture once;
  the sweep covers `test_maintenance.py`'s pre-existing tests too (86 spellings), plus
  `FixtureFile` and `ForkCheckout.own_file()` for the repeated file names. The sweep's
  scope was the user's call, made in session; the file-name half was mine, and the reply
  offers to take it back out.
- **2026-09-21, two threads on `test_maintenance.py`** (hard-coded label and session
  strings): answered and resolved. Fixed as `608b72e92` **on #185's branch**, not here,
  on the user's instruction that a change to what an earlier open pull request introduced
  belongs there and comes back by merge. `StackLabel` joins `StackBranch` in
  `constants.py` and `make_configuration()` builds from it in both suites;
  `A_SESSION_LINK` replaces the six spellings of one sample URL. `DEFAULT_STACK_TOML`
  keeps its literals - it is the document the loader parses. Merged back as `9cf9f2815`;
  680 pass, 665 on the base.

## The sweep now lives on #185

The whole naming sweep moved with it: `StackBranch`, `StackLabel`, `A_SESSION_LINK`,
`FixtureFile` and `ForkCheckout.own_file()` are on `claude/plan-item-kickoff-workflow-cuare2`
(`608b72e92`, commented on #185), so this branch's diff no longer changes a test it did not
add - 537 insertions over 11 files, against 37 deletions that are all its own. What stayed
is what only a three-deep stack needs: `StackBranch.GRANDCHILD`, `StackBranch.OFF_THE_CHAIN`
and `ForkCheckout.published_file()`.

If #185 is ever rewritten or abandoned, that commit is what this branch loses.

## Next

- Nothing outstanding on the branch. It waits on review, and on #185 landing before it can.
- `test_stack.py`'s older tests still spell their branch names per test (`engine`,
  `parser`, `wip`, `stuck`). Offered in the review reply, not done: they read as each
  test's own role rather than a shared vocabulary. That sweep would belong on #185 too.

## Decisions made while implementing

- The selector walks `Branch.parent`, not git containment, against the roadmap's wording.
  Reasons in the roadmap section and the PR description; it is the one call a reviewer
  should check.
- A chain stops at a branch that has landed: what sits above it needs a reparent onto the
  upstream base, which the whole-board pass owns.
- `ConflictResponse.chosen_for()` couples the response to the subtree argument rather than
  adding a second knob, so there is no way to run a whole-board pass that swallows conflicts.
- The document is linked from SKILL.md rather than named by a new config constant: one
  reader, and it keeps the item out of a second contended file.

## Worth knowing

- `plan_item_bootstrap.py` `open`/`record` cannot write this plan's manifest from this
  base: it hardcodes a four-space item indent and this manifest writes items flush with
  `items:`. That is #160's bug, whose fix is riding #151 and has landed on neither. The
  manifest was written by hand in its own style and pushed with `save-plan.sh` instead.
- `.claude/skills/plan-item-resolve/SKILL.md` on this base carries the same
  `in_review_label` bullet twice, once naming `basstler/stack.toml` and once
  `.claude/stack/stack.toml` - a merge residue on #185, not this item's to fix.
