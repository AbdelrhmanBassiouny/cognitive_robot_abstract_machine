# a-look-is-described-by-a-match (PR #275, draft)

Plan `knowledge-directed-requests`, track `method-selection`. Base
`claude/plan-item-kickoff-perception-idzwsk` (#266), with #259 merged in.

## The plan

Apply #266's shape - a `Look` subclass holding the world's own entities, a
`PerceptionDetector` stating its own capability, and a rule tree built by
`EQLSingleClassRDR.from_underspecified(a(TheLook)(detector=...))` - to the two
families that still predate it.

1. Merge #259 (`claude/plan-item-kickoff-kdp-34snn0`) in. Three additive conflicts:
   `exceptions.py`, `pipeline.py`, `test_montessori_perception_backend.py` - keep both
   sides. Verify both siblings' tests still pass.
2. `SoughtSurface` -> a `Look` with an open `finder` slot; `SurfaceFinder` ->
   `PerceptionDetector[SoughtSurface]`; `SurfaceRules` -> `from_underspecified` fitted
   through an `Expert` with `state_the_detectors_own_condition`. Deletes the
   hand-built `entity()/refinement()/Alternative.insert_at` tree and the re-declared
   `capability`/`stated_surface`/`answerable_surfaces`/`answers` quartet.
3. `TargetOnSurface`'s three copied fields -> the surface and the target themselves,
   with the readings restated as properties over them, plus an open `detector` slot.
   `DetectorRules` -> `from_underspecified` like the others.
4. Docstrings, `scripts/format_docstrings.py`, full experiments test run.

Tests first for each of 2 and 3.

## Settled while planning

- The item's title says "not by a case class", but `UnderspecifiedMatch.case_type` is
  `match.type` and its target is an attribute of that type, so a match over a bare twin
  entity is not something the engine can take. The item's own notes already resolved
  this: what is left is *the vocabulary the conditions are stated in*, not eliminating
  the case class. A `Look` that holds the world's entities is not a flattening.
- Every path this touches is absent from `main` (all three files come from unlanded
  siblings). It still gets its own branch because it changes files from *three*
  different in-flight branches - there is no single parent to fold into.

## Done

- Branch cut from #266, bootstrap commit pushed, draft PR #275 opened.
- `plan.yaml` (branch/PR/session/status) and the roadmap section recorded on
  personal-notes.

## Next

Step 1 - merge #259 in and resolve the three conflicts.

## Blocked / to report

- `subscribe_pr_activity` on tracking issue #201 was refused by the permission
  classifier, so this session will not see structural changes announced there.
- `.claude/hooks/plan_item_bootstrap.py`'s `apply_item_fields` writes a rewritten
  `status:` line at 4-space indent when it follows a `depends_on` list, producing
  invalid YAML and failing both `open` and `record`. Pre-existing (reproduces on
  untouched items). Worked around by hand-patching; wants its own bug-fix PR off `main`.
- `test_each_lib` is red across the whole stack from #222 onward, waiting on #251.
