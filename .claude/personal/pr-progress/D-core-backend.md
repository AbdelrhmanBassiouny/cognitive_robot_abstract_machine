# d-core-backend (PR #210, branch `D-core-backend`, base `D-core-single-class`)

Last slice of #68's three-way split: `d-core-expert` (#98) -> `d-core-single-class`
(#159) -> **this**. Kicked off in `auto` mode; full rationale in the plan's
`roadmap.md` section 31.

## Plan

1. `rdr/backend.py` - port `RDRBackend` from the mega-branch with #68's eleven
   `backend.py` threads applied:
   - `GroundTruth` = the callable only.
   - `ModelKey` = frozen dataclass (`case_type`, `attribute_name`), with
     `from_attribute` replacing the module-level `key_from_attribute`.
   - `fill_in_place` -> lazy `infer` (yields `UnificationDict`) + eager `fill`.
   - `query: Match` everywhere, `_key` -> `_key_for`, docs on every method/param.
2. Two changes forced by what landed under this branch: `fit` calls
   `EQLSingleClassRDR.fit(cases, targets, expert)` once (per-case `fit_case` would
   save per case since #159 and would not converge), and the no-ground-truth path
   passes `targets=None` rather than a sentinel (`UNSET` is gone).
3. `test/krrood_test/test_eql_rdr/test_rdr_backend.py` - pytest, over
   `expert_doubles.py` + `ZooDataset`. Drop the mega file's adapter and
   `from_underspecified` classes (already covered on #64/#159). Tests first.
4. Verify: mutation-check each assertion; compare sorted collected ids against the
   branch point, never counts; run `scripts/format_docstrings.py` on the two files.
5. Rewrite #210's description to match what landed; keep it a draft.

## Done

- Branch cut from `origin/D-core-single-class`, bootstrap commit pushed, draft
  PR #210 opened.
- `plan.yaml` updated (status `in_progress`, PR 210, session) and roadmap section 31
  appended; both pushed via `save-plan.sh`. Patched by hand because
  `plan_item_bootstrap.py`'s indentation defect (section 20) is still unfixed.
- Local 3.12 venv with editable `random_events`/`probabilistic_model`/`krrood`.

## Next

- Baseline `test_eql_rdr` collected ids on the branch point.
- Write `test_rdr_backend.py` failing first, then `backend.py`.

## Watch

- Expect no CI: the base #159 has queued nothing since 2026-08-13 and reads
  `mergeable_state: unknown`; section 21's base-move-then-push remedy is already
  known insufficient, so do not spend a push on it.
- The harness designated `claude/plan-item-kickoff-rdr-refactor-7c99yj`; the
  manifest and every sibling say `D-core-backend`, which is what is used (section
  20's precedent, confirmed with the developer then).
