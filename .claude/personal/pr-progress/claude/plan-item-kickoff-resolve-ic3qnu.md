## Next
- Nothing outstanding on the branch. It waits on review, and on #185 landing before it can.
- `test_stack.py`'s older tests still spell their branch names per test (`engine`,
  `parser`, `wip`, `stuck`). Offered in the review reply, not done: they read as each
  test's own role rather than a shared vocabulary. That sweep would belong on #185 too.


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
