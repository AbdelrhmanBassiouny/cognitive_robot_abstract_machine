## `--tooling` filter for `integration.py build`

**Branch** `claude/tooling-filter-integration-build-6edarh`, re-cut from
`claude/ready-tooling-integration-fkd5b5` (#284, which owns the tooling label's
meaning and gets `Configuration.tooling_label` from #281). PR base will be #284.

**Goal** `integration.py build --tooling` carries only the tips whose fork pull
request carries `Configuration.tooling_label`, reporting the rest under a new
`TipStatus` member the way `ANOTHER_PLAN` does on the plan-filter branch.

**Note** the `--plan` filter (`integration_plans.py`) is *not* on this base - it
lives on `claude/plan-item-kickoff-workflow-ixbvxl`. So this mirrors its shape
(`leaves_out` returning a `TipStatus | None`, threaded through
`select_for_build`/`tips_of`/`build_integration`) without being able to share a
type with it yet. Whoever lands second unifies the two behind one protocol.

**Plan**
1. `TipStatus.NOT_TOOLING` in `integration_tips.py`.
2. New `integration_tooling.py` with `ToolingFilter`.
3. Thread it through `select_for_build`, `tips_of`, `build_integration`.
4. `--tooling` flag on `BuildCommand`.
5. Tests in `.claude/stack/tests/test_integration_tooling.py`, written first.
6. `scripts/format_docstrings.py` on everything touched.

**Status** starting - nothing implemented yet.

**Next** write the failing tests.

**Known collision** #284 and #285 both add to `.claude/stack/maintenance_github.py`
- independent additions, trivially resolvable; not this branch's problem to fix.
