
# holes-fitted-like-pieces (PR #236, branch claude/plan-item-kickoff-ge8541)

Plan item `holes-fitted-like-pieces` of `knowledge-directed-perception`, stacked on #232
(`pieces-looked-for-where-expected`). Kicked off 2026-09-01 in `auto` mode.

## The plan

Find the board's six holes by fitting its one rigid, mesh-known layout over the lid -
three degrees of freedom for all six together, seeded from the board detection - instead
of classifying each dark contour on its own. Each hole's identity then comes from the
model, and the fitted placement *is* the board's pose, since the mesh's hole centres are
in the board's own local frame.

1. Extract `PieceMatcher`'s coarse-then-fine placement sweep into `OutlineFitter` over a
   `KnownOutline` (declared where both `KnownPiece` and the hole layout can reach it), so
   the layout fit reuses #232's evaluator rather than writing a second copy.
2. `BoardHoleLayout` in `hole_geometry.py`: the mesh's six footprints as one rigid
   outline, cached so the STL is not re-sliced per frame.
3. `BoardDetector`: the hole-sized dark patches become a *seed* (centre + long axis)
   rather than classified holes; the layout fit settles the board pose and every reported
   hole. `classifier` field goes.
4. Tests at three levels: the layout alone, the rendered scene, then the captures.

## Done so far

- Context gathered: manifest, roadmap in full (2570 lines), dependency readiness
  (`open_ready` on #232), scope check, parent's code read.
- Branch re-cut from #232's tip `bc0a17d2` (it had arrived cut from `integration`).
- Draft PR #236 opened; manifest and roadmap section saved to personal-notes.

## Next

- Write the failing tests first, then the layout fit.
- Measure cost as a ratio to a same-run baseline, never in seconds.
- Report whether the `non_inserted_objects` table-ghost mark actually comes off.

## Open, to raise on the PR rather than decide

- `CrossSectionClassifier` / `FootprintClassifier` become used by nothing but their own
  tests. `AGENTS.md` says consult before removing; asked on the PR, left standing.
- Whether the board's extent should come from the mesh rather than `BOARD_SCALE` - the
  last scene constant `pipeline.py` still imports. Taken only if it falls out cleanly.

## Known hazards

- The bootstrap script's four-space indent fault (#231's finding, same family as #160) is
  unfixed; `plan.yaml` was edited directly.
- #223's `Footprint` -> `RectifiedFootprint` rename will conflict with `pipeline.py` and
  `detections.py`, mechanically.

