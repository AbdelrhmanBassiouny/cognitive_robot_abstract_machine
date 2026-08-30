## #151 — manifest-currency-first, plus the folded `update` YAML fix

**Branch:** `claude/plan-manifest-update-priority-ex2zst`, not the designated
`claude/plan-item-bootstrap-yaml-tr8xyq` (which is the integration tip and carries no
work). The fold onto #151 was approved in plan mode this session.

### Why this session was on #151

`/add-plan-item` was run on a report that `plan_item_bootstrap.py update` emits invalid
YAML. The scope check placed it inside two unlanded branches rather than as new work:
#151 introduces the `update` subcommand and `manifest-staleness.md`; #160 fixes the
hardcoded indent but predates `update` entirely. Neither alone gives a working `update`,
and they conflicted. The user chose the fold into #151.

### Done — the work is finished and pushed

1. Both manifests carry the decision; `manifest-currency-first`'s `session` moved here,
   `plan-item-bootstrap-yaml-indent` records that nothing more is pushed to #160. Both
   roadmaps carry the reasoning, both dashboards republished, #102 has the structural
   comment.
2. Failing tests first: a `a-stacked-item` fixture with a written-out `depends_on`, three
   tests through `update`, and a parameterized round-trip contract over every
   scalar-styled key. 25 failures before, 0 after.
3. #160 merged in — 6 hunks in the module, 3 in its tests. `ItemIndentation` carried
   through to the sequence-entry and block-body render paths it never saw; exit codes 9/10
   collided and the save's two moved to 11/12; `ItemStatus` kept its single shared
   definition.
4. `render_scalar` hands quoting to PyYAML, values keep their own types, and `depends_on`
   is declared `SEQUENCE` with `value_span` widened for entries flush with their key.
5. 649 tests green across the four CI directories; `format_docstrings.py` clean. The
   reported reproduction re-run end to end against `rdr-interface-and-decorator` for both
   `D-ui` and `D-store`: exit 0, `depends_on` intact, byte-identical manifest.

Pushed as `0bc24dcc`. #151 is back to draft, carries the `bug` label #160 had, and its
description's open ordering question is rewritten to record the settled fold.

### Outstanding

- CI run 33340371549 was still in progress when this session ended. The previous head
  (`fb1a5a4a`) was green and this diff is `.claude/`-only.
- #160 is left open and untouched; it is superseded by this merge and is the user's to
  close.
- The three review threads #151 already had open are unchanged — none of them touch this
  work.
