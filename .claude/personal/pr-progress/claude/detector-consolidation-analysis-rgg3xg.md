## EdgeFitDetector / ColorBlobDetector consolidation

Branch `claude/detector-consolidation-analysis-rgg3xg`, re-cut from
`claude/icra-experiments-simulation-pipeline-w4ep7n` (`integration` carries no detector
code). Draft PR #299, based on that same branch. Base merged in at `dae41889c`.

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
  8 ms of fitting against 16, 86 ms against 97 for a whole look. Four runs, stable.
  My earlier 3% figure was taken under load and was wrong - it is nearer a tenth.

### Left undone, deliberately

- The tight configuration still claims it can answer a look for a piece with no modelled
  outline. Composing that into the capability refines the wrong node of the rule tree
  (the two conditions share an expression node), so the added-rule test fails. Conditions
  left exactly as they were. Pre-existing and separable.
- Annotating `finish`/`color` on `recorded_setup.lid_surface()` would make the captures
  exercise the colour path and change what the regression set measures. The user's call.

### Verification

`test/experiments_test` cannot be collected here (ORM generation needs ROS, as
`5382c1b2` also recorded). Modules run directly instead, all passing: detector_choice
31, hypotheses 21, piece_matching 33, perception 25, expectations 32, occupancy 22,
explanations 16, look_choice 17. Four `search_narrowing` failures reproduce on the
unmodified tree - an artifact of running without pytest's fixtures.

Harnesses in scratchpad: `regression.py`, `cost_after.py`, `run_with_fixtures.py`,
`pose_compare.py`, `which_detector.py`, plus the pre-collapse ones.

### Open

- Attribution conflict: AGENTS.md forbids a `Co-Authored-By` trailer for an assistant;
  this session's harness requires one. Followed the branch's existing convention (both
  trailers plus a plain "Made with the help of Claude." line). Worth settling.
