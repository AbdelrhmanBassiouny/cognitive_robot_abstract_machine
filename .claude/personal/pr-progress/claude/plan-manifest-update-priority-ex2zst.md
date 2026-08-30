## #151 — manifest-currency-first, plus the folded `update` YAML fix

**Branch:** `claude/plan-manifest-update-priority-ex2zst` (not the designated
`claude/plan-item-bootstrap-yaml-tr8xyq`, which is the integration tip and carries no
work — the fold onto #151 was approved in plan mode this session).

### Why this session is on #151

`/add-plan-item` was run on a report that `plan_item_bootstrap.py update` emits invalid
YAML. The scope check placed it inside two unlanded branches rather than as new work:
#151 introduces the `update` subcommand and `manifest-staleness.md`; #160 fixes the
hardcoded indent but predates `update` entirely. Neither alone gives a working `update`,
and they conflict (6 hunks in the module, 3 in its tests). User chose the fold into #151.

### Plan

1. ~~Record the fold in both manifests, republish both dashboards, comment on #102.~~ **Done.**
2. Failing tests first: an item whose `depends_on` is a written-out block sequence written
   through `update`; a `PLAIN` scalar containing ` #` round-tripping equal; replacing
   `depends_on` not orphaning its entries.
3. Merge #160; keep #151's `update`/`SEQUENCE`/`BLOCK` machinery, adopt `ItemIndentation`
   as the single source of indentation and carry it into the sequence-entry and block-body
   render paths #160 never saw. Adopt `PlanSaveFailedError`/`PlanNotWrittenError`.
4. Delegate scalar emission to PyYAML so a value with ` #` is quoted while
   `pull_request_number` stays an integer; declare `DEPENDS_ON` as `SEQUENCE`.
5. Run the three suites and `format_docstrings.py`, re-run the original reproduction
   end to end, push, re-draft #151, update its description.

### Done so far

- Both manifests carry the decision; `manifest-currency-first`'s `session` moved to this
  session, and `plan-item-bootstrap-yaml-indent` records that nothing more is pushed to it.
- Both roadmaps carry the reasoning; both dashboards republished; #102 has the structural
  comment.
- Reproduced all three defects locally against the live `rdr-interface-and-decorator`
  manifest before writing any of it down.

### Next

Step 2 — the failing tests.

### Outstanding / worth knowing

- #151 is currently **not a draft**. Flagged in the approved plan; re-draft after pushing
  per the standing convention.
- The reported blocker example for the ` #` truncation does not reproduce — blockers are
  quoted or folded and round-trip. The defect is on `PLAIN`-styled keys.
