## #232 - `pieces-looked-for-where-expected` (knowledge-directed-perception)

Branch `claude/plan-item-kickoff-kdp-o4l189`, draft PR #232, based on #225
(`claude/plan-item-kickoff-kdp-z4pv7l`, tip `a35243e8`). Kicked off in `auto` mode.

### The plan

Detection becomes the evaluation of hypotheses rather than the classification of blobs.
Colour is currently a gate: only a contour surviving the hue mask reaches
`PieceMatcher.match`, so a piece wearing the lid's hue or touching another is never
fitted. Measured: seeding the matcher at the places the board reports reaches 0.62-0.89
where the bottom-up pass finds nothing, at 0.05 s against 0.25 s for a full pass.

1. `perception/hypotheses.py` (new) - `BelievedPlace` (a region of a named surface and an
   interval of yaw) and `PieceHypothesis` (what is expected, where it is believed to be,
   which belief it came from). `BelievedPlace` is the type #227 deferred to this item.
2. `piece_matcher.py` - `match` takes a hypothesis; radius, step, angle set and candidate
   list read from the belief instead of fixed.
3. `pipeline.py` - three hypothesis sources: a colour blob (as today), the board's
   detected holes, and the pieces the world places. Colour becomes evidence, not a gate.
4. `detections.py` - a detection carries the hypothesis it came from.
5. Tests first at three levels: the types, the matcher, then the rendered scene and the
   six captures.

### Done so far

- Gathered the item's context; dependency #225 reports `open_ready`.
- Scope check run: ordinary stacking, and the purpose check against #227 comes back clean
  (it deliberately did not build the believed place).
- Branch re-cut from #225's tip (it had arrived cut from `integration`), pushed, draft
  #232 opened.
- `plan.yaml` records branch/PR/session/`in_progress`; roadmap section appended.

### Next

- Write the failing tests, then the three modules, in the order above.
- Measure and record: which of the four `LID_PIECES_STILL_MISSED` marks come off, the
  false-positive count per capture, and `detect`'s cost against the parent's 0.279 s.

### Watch out for

- **This item will add ghosts as well as pieces.** A prism template near the board's
  middle reaches 0.85-0.89 with no prism there, above every genuine lid piece. Separating
  them is `competing-explanations`, which depends on this. The recall test is a subset
  assertion so it will not catch them; `test_only_the_pieces_resting_on_the_table_are_
  detected_there` is exact, and a regression there is a blocker to report, not absorb.
- Open at implementation time: how the footprint and height of a seeded (contour-less)
  fit are measured, since both currently read a segmented contour.
- Landing hazard: #223's `Footprint` -> `RectifiedFootprint` rename.
