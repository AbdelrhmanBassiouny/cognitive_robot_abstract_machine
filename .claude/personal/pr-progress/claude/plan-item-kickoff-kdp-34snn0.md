# `surfaces-found-by-looking` - PR #259 (draft)

`knowledge-directed-perception`, `method-selection` track. Branch
`claude/plan-item-kickoff-kdp-34snn0`, one commit (`f87d0b17`) off **#231**
(`claude/choose-detection-method-gf64yp`) - not #222, because
`WorkspaceSurface.finish` and the capability/rule-tree mechanism are #231's.
`depends_on` now records `choose-detection-method` alongside #222 and #216.

## Built

- `surface_finding.py`: `SoughtSurface`, `SurfaceFinder` +
  `ModelledSurfaceFinder`/`MeasuredSurfaceFinder`, `SurfaceRules`.
- `pipeline.table_in(frame)`, used by `detect` and by the drawn windows;
  `rectify` takes a surface, `searched_surfaces` takes the table it searches.
- `recorded_setup` states that Tracy's table is brushed steel.
- `orthophoto`: `ImageWindow` + `WorkspaceBox.window_in`, with `clip` rewritten
  in terms of them.

## Measured

- Searched stretch 0.635 m2 (tuned) -> ~0.51 m2, and the untuned 1.2 m2 reaches
  the **same** answer on all six captures. The tuning no longer decides.
- 5/6 captures bit-identical to the parent; the 6th moves one prism 0.15 mm /
  0.02 agreement, a two-valued fit that exists on the parent too.
- `detect` 1.07x the parent, same-run interleaved. Measurement 0.061 s/frame
  after reading only the pixels the surface's own space covers (was 0.100).
- 429 passed / 1 skipped / 16 xfailed vs 390 / 1 / 16 on the parent.

## Decided along the way

- Only the extent is measured; the height stays the world's (it is recorded as
  agreeing, and the lid's plane is derived from it).
- Measured corners land on the modelled region's own grid - #238's lattice rule,
  now pinned by a test.
- The measurement declares it needs depth: #231's rendered fixture draws none.

## Outstanding

- `tune_workspace` is used by nothing but its own tests now; removal **asked on
  the PR**, not taken.
- #239 states the same finish on the twin's own surfaces - complementary, not a
  duplicate; whichever merge happens first keeps #239's for the world.
- Tracking-issue subscription was refused by the permission classifier, so this
  session sees no structural plan changes as they arrive.
- `plan_item_bootstrap.py open` hit the known 4-space indentation fault (7th
  round on this plan); `plan.yaml` edited directly.

Per my notes: opening the PR ends this session's obligation to it. No watching,
no scheduled checks.
