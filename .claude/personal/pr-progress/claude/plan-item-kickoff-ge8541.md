
# holes-fitted-like-pieces (PR #236, branch claude/plan-item-kickoff-ge8541)

Plan item `holes-fitted-like-pieces` of `knowledge-directed-perception`, stacked on #232.
Kicked off 2026-09-01 in `auto` mode. Built and pushed; waiting on your review.

## What is on the branch

1. `OutlineFitter` over a `KnownOutline` - `PieceMatcher`'s sweep extracted, bit-identical
   on a fixed input. `KnownPiece` and `BoardHoleLayout` are both `KnownOutline`s.
2. `BoardHoleLayout` in `hole_geometry.py`: the mesh's six footprints as one rigid outline,
   cached, and carrying the size the board actually is.
3. `BoardDetector` fits that layout - rough over the whole turn, then careful - and the
   placement *is* the board's pose. `classifier` gone; `BOARD_SCALE` no longer imported.
4. `BoardDetector.measure_scale` + `recorded_setup.BOARD_SCALE_AGAINST_THE_MESH = 0.865`.

## The finding that changed the item

The mesh is not cut to the board the captures hold - scale 0.854 by similarity on the four
unambiguous holes (2.1-2.6 mm residual; 5-10 mm at scale 1), individual holes smaller in
the same proportion, and no rectification plane closes it without putting the holes below
the table. Your direction was to treat that as a law broken, find the hypothesis that mends
it, and persist it - which is what `measure_scale` and the recorded constant do.

Board now at (0.805, 0.10) within 1.5 degrees in all six captures (parent: 0.791-0.804,
-5.6 to -29.7 degrees), all six holes over openings.

## Outstanding, for you

- **`CrossSectionClassifier` / `FootprintClassifier`** are used by nothing but their own
  tests now. AGENTS.md says consult before removing; asked on the PR, left standing.
- **One regression, marked**: `tracy_pickup_demo`'s lid cylinder is displaced by a prism
  fitted to the round hole's rim, 0.682 against 0.673. Pre-existing ghost that a mis-placed
  board had been hiding; marked against `competing-explanations`.
- **Cost**: 0.560 s/frame against 0.370 s, over the node's 0.5 s period. #231's
  `RectifiedFrame` and a believed place from the previous frame are the two ways back.
- **0.865 is six looks from one angle.** Measuring the real board would settle it, and would
  say whether the mesh should simply be re-cut.

## Verified

423 passed, 1 skipped, 5 xfailed across `test/experiments_test/` against 400/1/11 on the
parent. Environment: `pip install -U uv` first (the PATH `uv` cannot parse the workspace).

