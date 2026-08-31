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

### Outstanding

- Nothing on this session's side. CI has not reported yet at the time of the push.
- Landing hazards on the PR: #223's `Footprint` -> `RectifiedFootprint` rename; #223
  meeting `PieceHypothesis.candidates` (a tuple of dataclasses) when it walks this
  package for the ORM; and #231's `LoosePieceDetector` -> `EdgeFitDetector` rename, which
  changes the same `detect` this branch rewrites - the only conflict of the three that is
  not purely mechanical.
- Environment note worth keeping: this container's default `uv` (0.8.17) cannot parse the
  repo's `pyproject.toml`; `/usr/local/bin/uv` (0.12.7) can. `docformatter`/`black` need
  installing before `scripts/format_docstrings.py` runs.
