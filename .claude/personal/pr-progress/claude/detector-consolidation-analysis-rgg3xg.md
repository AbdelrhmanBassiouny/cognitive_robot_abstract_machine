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
  8 ms of fitting against 16, 86 ms against 97 for a whole look. Four runs, stable.
  My earlier 3% figure was taken under load and was wrong - it is nearer a tenth.

### CI, first run

`test_each_lib (experiments)` failed with ten tests. Nine were
`sqlalchemy.exc.InvalidRequestError: Table ... is already defined` from the ORM
interface, inherited from the stale base: the base branch cleared them when it merged
`claude/recordedlook-orm-conflict-n13p05`, and this branch has now merged the base. That
path cannot be run here at all - `scripts/regenerate_all_orm.py` still dies on
`CouldNotResolveType: DebugExpressionPublisher` for want of ROS.

The tenth was this branch's own:
`test_a_colour_read_for_its_own_place_fixes_it_at_its_rectangles_turn`, expecting 0.2967
rad and getting -1.2723 - exactly a quarter circle apart. `PlaceToScoreAt` read
`cv2.minAreaRect`'s angle raw, and which side OpenCV names varies with its version
(4.11: `(40, 20)` at 17 degrees; 5.0: `(19.9, 40.9)` at -72.9). `RectifiedFootprint.
from_contour` already brought the angle onto the longer side, but that reading was buried
in it.

Fixed by making the enclosing rectangle a thing: `EnclosingRectangle.around` states the
convention once and both readers use it. Detection is unaffected - `QuarterTurns` offers
the same four turns either way. Reproduced the failure on opencv 5.0.0 in this container
before fixing it, and verified on both versions after.

### Left undone, deliberately

- The tight configuration still claims it can answer a look for a piece with no modelled
  outline. Composing that into the capability refines the wrong node of the rule tree
  (the two conditions share an expression node), so the added-rule test fails. Conditions
  left exactly as they were. Pre-existing and separable.
- Annotating `finish`/`color` on `recorded_setup.lid_surface()` would make the captures
  exercise the colour path and change what the regression set measures. The user's call.

### Verification

`test/experiments_test` cannot be collected here (ORM generation needs ROS, as
`5382c1b2` also recorded). Modules run directly instead, on both opencv 5.0.0 and
4.11.0.86, all passing: footprint 9, detector_choice 31, hypotheses 21, piece_matching
33, perception 25, expectations 32, occupancy 22, explanations 16, look_choice 17,
search_narrowing 27. The `search_narrowing` failures the runner used to show are gone
since the second base merge. `detection_on_captures` cannot run in the runner at all -
it wants pytest's `request` fixture - but `regression.py` exercises the same path.

Harnesses in scratchpad: `regression.py`, `cost_after.py`, `run_with_fixtures.py`,
`pose_compare.py`, `which_detector.py`, plus the pre-collapse ones.

### Open

- Attribution conflict: AGENTS.md forbids a `Co-Authored-By` trailer for an assistant;
  this session's harness requires one. Followed the branch's existing convention (both
  trailers plus a plain "Made with the help of Claude." line). Worth settling.
