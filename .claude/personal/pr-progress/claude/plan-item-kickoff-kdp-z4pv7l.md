# one-detection-per-thing (PR #225, off #221)

Plan: knowledge-directed-perception, `surfaces` track. Branch cut from
`perception_per_supporting_surface` at `df667585e` (the session's branch arrived cut from
`integration` and was reset onto the parent before the first commit).

## The plan

Nothing may be reported in a place something else already occupies. A place is the volume
a detection takes up - its own world-frame outline, between `surface_height` and
`top_height`, both of which `MontessoriDetection` already reports. Two volumes are one
place when their outlines overlap in plan view *and* their height spans overlap; the
height half is what keeps a piece resting on the lid (above the board) apart from a ghost
reported inside the board at the table's plane.

What already occupies a place:
1. The board as seen this frame - it stands from the table to its lid, so anything at the
   table's plane within its outline is its own edge or a ghost of what stands on it. The
   detected board, not the modelled one, because the world's board pose has drifted.
2. Another detection - keep the stronger `outline_agreement`.
3. A body the world knows about, excluding what perception measures itself (table, board,
   pieces). `is_place_occupied` is what the item's note names; its per-frame cost is
   measured before it is adopted, since `detect` already costs 0.35 s of a 0.5 s period.

## Done

- Context gathered, dependency #221 `open_ready`, scope check run (overlap with #202/#205/
  #221/#223 as every round on this plan expects).
- Branch reset onto the parent, bootstrapped, pushed; draft PR #225 opened.
- Manifest updated (branch, session, PR, `in_progress`) and the roadmap section written.

## Next

1. Reproduce the duplicate on the captures and measure it: the ghost's `outline_agreement`
   against the real detection's, and how much outline a ghost shares with the board.
2. Tests first: `test_montessori_occupancy.py` for the volume rule; a pipeline test on the
   rendered scene; then the captures.
3. Implement `occupancy.py`, the board's volume (its `surface_height` becomes the table it
   stands on, its `top_height` the lid), and the resolution pass in
   `MontessoriPerceptionPipeline.detect`.
4. Remove the strict expected-to-fail mark from
   `test_only_the_pieces_resting_on_the_table_are_detected_there`.
5. Measure the per-frame cost against the parent's 0.35 s and record it.
6. Keep #225's description in step with the branch; re-draft after every push.

## Open

- The shared-outline threshold is to be measured, not chosen, and recorded with its value.
- Landing hazard: #223's `Footprint` -> `RectifiedFootprint` rename conflicts with this
  branch's edits to `pipeline.py`/`detections.py`; resolution is mechanical.
