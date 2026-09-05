
# `surfaces-found-by-looking` - PR #259 (draft)

`knowledge-directed-perception`, `method-selection` track. Branch
`claude/plan-item-kickoff-kdp-34snn0`, off **#231** - not #222, because
`WorkspaceSurface.finish` and the capability/rule-tree mechanism are #231's.
`depends_on` records `choose-detection-method` alongside #222 and #216.

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
- `detect` 1.07x the parent, same-run interleaved. Measurement 0.061 s/frame.
- 430 passed / 1 skipped / 16 xfailed vs 390 / 1 / 16 on the parent.

## Review round of 2026-09-05 (five threads, none resolved)

Answered in code as `946017c70`: `SoughtSurface` was a copy of the surface's
finish, a constant that was always true, and a frame property. It now holds the
`WorkspaceSurface` and the `RgbdFrame`, and the conditions read into them. EQL
traverses nested attributes and properties (probed first) - so the flattening in
`TargetOnSurface` and `RequestedLook` was never needed either. `carries_depth`
moved onto `RgbdFrame`, `area` onto `WorkspaceRegion`, and `find` takes the pair.
One test added, pinning that the finish deciding a look is the one a twin Body's
own collision shape states.

Four left open with replies, each answered differently from what it asked:

- finish on the twin's body -> #239 states it for the world, #238's
  `recorded_world` already has bodies for the recording; a third copy here is the
  duplication this plan has paid for. Fold: `_body_of` passes `surface.finish`
  into its `Box`.
- description as a `Match` read by an EQL-RDR -> needs the #77 stack; proposed as
  the item `a-look-is-described-by-a-match`, which would also remove
  `TargetOnSurface` and `RequestedLook`. **Not added - his call.**
- camera calibration, and combining the two finders -> proposed as an item;
  arrives as a third `SurfaceFinder` and one `add_rule`. Caveats measured: the
  transform is already good to ~1 mm here, and #236's 0.865 board is a wrong
  model rather than a wrong pose. **Not added - his call.**

## CI

`test_each_lib (semantic_digital_twin)` red on the previous head:
`test/conftest.py`'s module-scoped `count_worlds`, with 1494 passed and no
failing assertion. The diff is experiments-only, base #231 is green on that job
with identical sdt sources, and #231 is red on `krrood` instead. Not this diff -
comment posted, and the push of `946017c70` re-runs it.

## Outstanding

- `tune_workspace` used by nothing but its own tests; removal **asked on the
  PR**, not taken.
- Tracking-issue subscription refused by the permission classifier, so this
  session sees no structural plan changes as they arrive.

Per my notes: opening the PR ends this session's obligation to it. No watching,
no scheduled checks.

