## EdgeFitDetector / ColorBlobDetector consolidation

Branch `claude/detector-consolidation-analysis-rgg3xg`, re-cut from
`claude/icra-experiments-simulation-pipeline-w4ep7n` (`integration` carries no detector
code). PR #299, based on that same branch - the user took it out of draft, so it stays
ready. Base merged in twice, at `dae41889c` and again at `06e7af3eb`.

**Done and pushed.** Analysis, then the collapse, then the regression.

### What landed

One detector configured twice. `PlaceOfASeenColor` states how much of a colour blob is
taken on trust: `PlaceToSearchAround` (seeding reach, any turn) and `PlaceToScoreAt`
(radius 0, the rectangle's four turns). `BelievedPlace.yaw` widened to a `BelievedYaw`
so `QuarterTurns` can sit beside `YawInterval`. `ColorBlobDetector` and
`PieceMatcher.match_at` are gone.

The defect it closes: `ColorBlobDetector.detect` never read `surface_pass.expected`, so
on a matte surface a knowledge-directed expectation was silently dropped - `d8b65443`
added that path to the edge fit alone. Proven with a failing test first, then fixed by
the collapse itself.

### Measured

- Six captures, before and after: **6 missed / 2 invented, board 6/6**, on opencv
  4.11.0.86. Unchanged, and it cannot change - `recorded_setup` states neither `finish`
  nor `color` for the lid, so every look there falls to the edge fit. The captures guard
  the edge-fit path; they are not evidence about the consolidation.
- `5382c1b2` recorded 6 missed / **1** invented. Missed reproduces; invented does not, on
  either opencv, before or after. Flagged in the PR, unresolved.
- Rendered matte lid: both configurations report the same category, outline, footprint
  and position. Footprint is now the fitted outline's for both (0.00090000 = 30 mm sq.)
  rather than the blob contour's 0.00085400.
- Cost, re-measured after the collapse (the tree's 89/126 ms predates `d8b65443`):
