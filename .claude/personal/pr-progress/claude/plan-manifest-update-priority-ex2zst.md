## Resolve of 2026-10-02 (session_01RAcB6RV7AtLyfuipHeMyw8) — current state

### Plan
1. Record the real blockers in the manifest and republish the dashboard (done).
2. Merge #185's head across the `bastler` → `basstler` rename: apply the substitution,
   record `213ad791c` as merged (`-s ours`), then merge the head (done: `2628b9959`,
   `4e83230aa`, `be1bd2f62`).
3. Reproduce the `integration-conflict` against `D-deco` (#77) and clear it if it no
   longer reproduces (done: it doesn't, so the label was removed).
4. Fix the `--append-notes` literal-note defect this round hit, failing test first (done:
   `e17bf4d5d`), and restore the manifest the defect damaged (done).
5. Update the PR description, roadmap, notes and dashboard (done).

### Done
- 809 tests pass under `test/basstler_test` on Python 3.12. The merged tree differs from
  #185's head on exactly this branch's 30 paths.
- Manifest: blockers cleared, note appended (14 paragraphs), roadmap section
  "`manifest-currency-first`: the rename merge of 2026-10-02" added.
- Labels: `integration-conflict` removed; `needs-resolution` left for the pass to clear.
- PR left out of draft: it carries `cram2-link-sent`, so it was apparently marked ready
  before; the user's convention is to leave a PR they marked ready as ready.

### Outstanding
- CI on `e17bf4d5d` had not reported when this session ended. GitHub's mergeability for
  the new head was still computing.
- `promotion-summaries-and-table`'s note in this plan still carries the same
  literal-note damage from an earlier append; it can be restored from that item's note
  history on the notes branch.

---

## History
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
