# one-detection-per-thing (PR #225, off #221)

Plan: knowledge-directed-perception, `surfaces` track. Branch cut from
`perception_per_supporting_surface` at `df667585e` (the session's branch arrived cut from
`integration` and was reset onto the parent before the first commit). Built as `cf155f4a1`.

## What it turned out to be

The plan described the duplicate as a detection standing inside the board's own volume. It
is not. Measured on the six captures, every duplicate lies 14-63 mm *outside* the board's
detected outline and shares no ground with it, so the planned volume rule rejects none of
them; real table pieces stand 115-186 mm clear.

What they are is the table seen *past* the board: a piece on the lid stands between the
camera and the table behind it, so the table's rectification places it there, outside the
board along the ray from the camera. The rule is therefore line of sight, not volume - the
board's outline projected away from the camera onto the table's plane, cast from the top of
a piece standing on the lid. The height half stands unchanged and is what keeps a piece
resting on the lid apart from a reading taken off the table below it.

## Done

- `perception/occupancy.py`: `OccupiedVolume` (outline + height span, `overlaps`, `hides`)
  and `Occupancy` (`claim`, `keep_one_detection_per_place`, best fit first).
- `pipeline.py`: `table_hidden_by`, claimed before the pieces are offered their places.
- `camera.py`: `RgbdFrame.camera_position`. `exceptions.py`: `NothingIsHiddenFromBelow`.
- 23 new tests. `219 passed, 1 skipped, 11 xfailed` against `191 / 1 / 16` on the parent.
- `detect` at 0.279 s per frame against the parent's 0.289 s.
- Strict expected-to-fail mark off five captures of six; `non_inserted_objects` keeps it,
  now naming `holes-fitted-like-pieces` (board read at -29.7 deg against -7.6 deg elsewhere,
  same centre, from five of six holes).
- Manifest, roadmap section, PR description all in step; #225 re-drafted after the push.

## Decisions recorded rather than left implicit

- **No threshold.** Two solid things cannot stand in one another, so any shared ground at
  meeting heights is one thing read twice. Measured: duplicates share their whole outline,
  separate detections share none. Nothing to tune.
- **`is_place_occupied` measured and not used**: 0.035 s per call against a fifteen-body
  world, so six detections cost 0.21 s of a 0.5 s period `detect` already spends 0.35 s of;
  reading every body's bounding box costs the same. A general per-frame walk of the world's
  bodies does not fit the frame budget - recorded as a finding for
  `detector-parameters-from-knowledge`, not dropped.

## Next

- Nothing outstanding on the branch. CI has not reported yet at the time of writing.
- Landing hazard: #223's `Footprint` -> `RectifiedFootprint` rename conflicts with this
  branch's `pipeline.py` and `test_montessori_perception.py` edits; mechanical.
