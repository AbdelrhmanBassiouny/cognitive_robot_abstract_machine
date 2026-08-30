# `detect-per-supporting-surface` -- PR #221, off #205

Plan item of `knowledge-directed-perception` (tracking issue #201), branch
`perception_per_supporting_surface`, kicked off 2026-08-30 in `auto` mode.

## Done -- the item is built and pushed

`2744c23d`. One detection pass per supporting surface, each rectified onto its own plane,
every detection attributed to the surface supporting it.

- `MontessoriPerceptionPipeline` holds `table` and `lid` as `WorkspaceSurface`es instead of
  `region`/`table_height`/`board_height` -- the restructure #205 left here.
- `SurfaceSearch` carries the part of a plane one pass may claim (the outline bounding the
  surface, the surfaces standing on it); `claims(x, y)` replaced `board.encloses -> skip`.
- The lid's height comes from the world, its extent from the detected board.
- `MontessoriShapeDetection.supporting_surface` names the surface, for `perception-backend`.
- `SurfaceColors.piece_mask` segments one colour at a time; `EdgeDistances.of` reads each
  colour channel; `Orthophoto` caches its hue-saturation-value form.
- Test renderer: `PlacedPiece.surface_height`, and `clear_lid_position()`.

`153 passed, 1 skipped` against the parent's `144 passed, 1 skipped` -- the nine added here.

## The two things the plan had not found

The item's note says "invisible twice over"; it is four. The restructure fixes two.

- The lid wears a piece colour (wood hue 19, amber prisms 21, tolerance 4), so one mask over
  all piece colours merged a piece on the lid into the lid.
- The edge fit ran Canny over brightness, where a cyan piece is **one** grey level from the
  lid and **34** from the bare table -- no edge to fit.

Both fixed inside the one detector, so `choose-detection-method` still owns choosing between
detectors. **But its "the lid selects the colour blob" rule loses its motivation**: the edge
fit now fits a cube on the lid at 0.93. Recorded on #201 and in the roadmap.

## Not done, deliberately

- `supporting_surface` is not populated (against `surface-finish-annotation`'s prediction).
- An amber piece on the wooden lid still cannot be separated by colour at all --
  `choose-detection-method`'s real case.
- `detect` costs 0.35 s per frame against 0.23 s; the node's period is 0.5 s.

## Next

Nothing outstanding in this session: PR #221 is open as a draft with its description matching
the work. CI has not been read yet.
