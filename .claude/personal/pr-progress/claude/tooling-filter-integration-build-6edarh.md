## `--tooling` filter for `integration.py build` - PR #293 (draft)

**Branch** `claude/tooling-filter-integration-build-6edarh`, re-cut from
`claude/ready-tooling-integration-fkd5b5` (#284). PR #293 is based on #284.

**Done** all of it, in one commit:
1. `TipStatus.NOT_A_TOOLING_CHANGE` (`not-a-tooling-change`, integrated=False).
2. `integration_tooling.py` with `ToolingFilter` (`over`/`unfiltered`/
   `is_filtering`/`leaves_out`).
3. Threaded through `select_for_build`, `tips_of`, `build_integration`, and the
   `build` test fixture.
4. `--tooling` flag on `BuildCommand`; README + `integration.py` docstring.
5. `.claude/stack/tests/test_integration_tooling.py` - 8 tests, written first;
   4 proven to fail against the pre-change selection code.
6. `scripts/format_docstrings.py` run on every modified file.

**Test state** `pytest .claude/stack/tests/` = 340 passed, 4 failed. The 4 are
pre-existing on #284's base (nested pytest in `test_integration_reproduction.py`
cannot import its `-p integration_reproduction` plugin in this environment); they
fail identically with this branch stashed. Not this branch's to fix.

**Left deliberately undone**
- No shared protocol with `PlanFilter`: `integration_plans.py` is not on this
  base (it lives on `claude/plan-item-kickoff-workflow-ixbvxl`), so the two
  cannot be unified until they meet. Flagged in the PR body for whoever lands
  second.
- No candidate-title work (`--plan` marks a filtered candidate as never
  publishable); that machinery is not on this base either, and the ask was the
  build filter only.

**Known collision** #284 and #285 both add to `.claude/stack/maintenance_github.py`
- independent additions, trivially resolvable; this branch touches neither.

**Next** nothing outstanding. Session's obligation ends with the draft PR opened.
