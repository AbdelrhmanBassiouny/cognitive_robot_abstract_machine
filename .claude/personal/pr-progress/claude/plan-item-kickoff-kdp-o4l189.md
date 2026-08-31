## #232 - `pieces-looked-for-where-expected` (knowledge-directed-perception)

Branch `claude/plan-item-kickoff-kdp-o4l189`, draft PR #232, based on #225
(`claude/plan-item-kickoff-kdp-z4pv7l`). Kicked off and built in `auto` mode.

### Built, pushed as `d8b654433`

Detection is now the evaluation of hypotheses rather than the classification of blobs.

- `perception/hypotheses.py` (new): `BelievedPlace` (a region of a named surface and a
  `YawInterval`), `PieceHypothesis`, `BeliefSource`, `SEED_REACH`.
- `piece_matcher.py`: `match` takes a hypothesis; reach, angle set and candidates read
  from the belief. `search_radius` and `hue_tolerance` moved off the matcher.
- `pipeline.py`: the detector evaluates every hypothesis its surface owns, colour being
  one source of them; `expected_pieces` believes from the world, which names which piece
  it placed where. Anything more particular is supplied by the caller via `expected`.
- `detections.py`: a detection carries the `hypothesis` it answered.
- `orthophoto.py`: `WorkspaceRegion.to_pixels`, the inverse of `to_world_position`.

**397 passed, 1 skipped, 11 xfailed** vs **376/1/11** on the parent - the 21 added and
nothing else moved. All six captures report **exactly** what the parent reported
(compared detection by detection), and `detect` costs **0.344 s** against the parent's
**0.344 s**.

### The one real decision, made on measurement

Sweeping the board's holes for pieces every frame was built first, and left out at the
developer's decision. It costs **1.7-1.9x the shipped frame time** and turns 3 false lid
reports into 20, in exchange for 3 of the item's 4 lid marks. Narrowing it - a hole
expecting only the pieces that fit through its measured opening, overlapping places
merged - takes a third off that cost but recovers only 2 of the 4 marks, because the hole
measurements it reads are the ones `holes-fitted-like-pieces` says are wrong. The first
reading of this was reported in seconds against the 0.5 s period and was wrong: this
container's speed moves between runs by more than the difference measured, so only a
ratio to a same-run baseline survives. The lid marks stay, now naming
`expectations-from-events` - the item that can say *which* piece at *which* hole, which
is what makes a seeded fit cheap and precise. Recorded in full in `roadmap.md`.

### Review round of 2026-08-31, pushed as `571042923`

Two threads, both on `hypotheses.py`, both answered and neither resolved.

- *"isn't this basically a 2D Pose? or a Point?"* - not a pose (a pose is one placement,
  a believed place is a disc of them and an interval of turns), but the centre is a point
  and is one now: `PlanarPoint`, moved with `PlanarSize` out of `hole_geometry.py` into a
  new `montessori/planar_geometry.py` and no longer worded as the board mesh's plane.
  `MatchedPiece.center` and `Orthophoto.contour_center` follow it. Not `Point2`: it is
  identity-equal - `Point2(0.6, 0.2) == Point2(0.6, 0.2)` is `False` - so as a field of a
  value object every belief about one place would compare unequal, and it drags casadi and
  a reference frame into a numpy sweep. Left open in case he wants `Point2` regardless.
- *"why is this a StrEnum?"* - it is not one any more. `BeliefSource` is an abstract mixin
  in `krrood/patterns/belief_source.py`, `World` inherits it in `semantic_digital_twin`,
  `LoosePieceDetector` inherits it here, and whoever asks for a look supplies itself; a
  belief keeps the source object, so `hypothesis.source is pipeline.world` and `is
  pipeline.piece_detector` are assertions. Left open because the `Expert` half is answered
  differently: krrood's RDR `Expert` is not reused or rebased on `BeliefSource`, since it
  answers questions about cases and says nothing about where a thing is, and no consumer
  wants the coupling yet.

**400 passed, 1 skipped, 11 xfailed** vs 397 before the round; one test added in
`semantic_digital_twin`, whose `test_worlds/test_world.py` failing set is byte-identical
with and without the `World` base change. The sdt ORM interface regenerates and imports
with the new base.

### Outstanding

- Nothing on this session's side. Both review threads are answered and deliberately left
  open for the developer: the `Point2`-or-`PlanarPoint` choice, and whether an RDR
  `Expert` should be a `BeliefSource`.
- Landing hazards on the PR: #223's `Footprint` -> `RectifiedFootprint` rename, now also
  meeting this branch's edit to `hole_geometry.py`; #223 meeting `PieceHypothesis.candidates`
  (a tuple of dataclasses) and `PieceHypothesis.source` (an abstract krrood mixin `World`
  also inherits) when it walks this package for the ORM; and #231's `LoosePieceDetector`
  -> `EdgeFitDetector` rename, which changes the same `detect` this branch rewrites and
  must keep its new `BeliefSource` base - the only conflict of the three that is not
  purely mechanical.
- Environment note worth keeping: this container's default `uv` (0.8.17) cannot parse the
  repo's `pyproject.toml`; `/usr/local/bin/uv` (0.12.7) can. `docformatter`/`black` need
  installing before `scripts/format_docstrings.py` runs, and it needs them on `PATH`, not
  only importable.
