# `detect-per-supporting-surface` -- PR #221, off #205

Plan item of `knowledge-directed-perception` (tracking issue #201), branch
`perception_per_supporting_surface`, kicked off 2026-08-30 in `auto` mode.

## The plan

Fault 2 of the plan's three: a piece on the board's lid is invisible twice over --
rectified onto the table's plane only, so parallax-shifted out of both silhouettes, and
then discarded because the board is coded as an obstacle. Both are the single
table-plane pass, so the fix is one pass per supporting surface.

1. `WorkspaceSurface` gains the name the world knows the surface by, for attribution.
2. `SearchedSurface`: one surface as one pass sees it -- the plane, the outline bounding
   the surface itself (the detected board, for the lid), and the surfaces standing on it.
   `claims(x, y)` replaces `board.encloses(x, y) -> skip`.
3. `MontessoriPerceptionPipeline` holds the table and the lid as surfaces, not
   `region`/`table_height`/`board_height`; `detect` runs the loose-piece detector once per
   surface at that surface's own plane.
4. Every detection records the surface supporting it.
5. Test renderer: `PlacedPiece` gains the height of the surface it stands on.

The lid's height comes from the world (rectification needs it before detection); its
extent from the detected board (the board moves, its height above the table does not).

## Done

- Branch, draft PR #221, manifest + roadmap section recorded.

## Next

- Failing tests first: a cube on the lid is found, at the lid's height, attributed to the
  lid; a piece on the table still attributed to the table; the lid still not a piece.
- Then the implementation, then the whole `test_montessori_*` suite against the parent.

## Watch for

- **The rendered lid wears the amber pieces' hue.** `LID_COLOR` is hue 19, `YELLOW_HUE` is
  21, `HUE_TOLERANCE` is 4 -- so `piece_mask` marks the whole lid, and an amber piece on it
  merges into that blob. The lid's own contour is size-rejected, so this costs nothing, but
  the lid test has to place a *cyan* piece (a cube), which is also what
  `demo-runs-on-grounded-perception` asks for. Whether an amber piece on wood is separable
  at all is `choose-detection-method`'s question, not this item's.
- A piece on the lid may also raise a parallax-shifted contour on the table pass. If its
  centre lands outside the board it would be a second detection of one piece. Assert
  exactly one; if it appears, decide here rather than deferring it into
  `one-detection-per-thing`, since this pass is what creates it.
