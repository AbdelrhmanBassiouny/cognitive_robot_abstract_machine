# competing-explanations (#270)

Plan item `competing-explanations`, now of **knowledge-directed-grounding** (tracking
issue #201) - the `knowledge-directed-perception` plan was split into three successor
plans, one per wave, on 2026-09-05 while this branch was being built; the item carried
over intact with its branch, PR, session and status. Branch
`claude/plan-item-kickoff-kdp-r8nttk`, stacked on #236, which carries #232. Kicked off
and built 2026-09-05 in `auto` mode.

## Done

- **Built and pushed as `ee52352e0`.** `perception/explanations.py` (new) holds the
  two-sided account, the board's own outlines cast into a fit's own plane, and the
  comparison. `PieceMatcher.minimum_agreement` is gone and `match` is `fits`;
  `MontessoriShapeDetection` carries its `explanation`; `Occupancy` reads the same
  comparison instead of raw agreement.
- `test_every_piece_resting_on_the_lid_is_found`'s `tracy_pickup_demo` mark reported
  itself stale and was removed. The other four are `expectations-from-events`'.
- **Review round of 2026-09-05 answered as `8443f6959`.** One thread: the test named
  after the belief claim never fed a belief in - it exercised `is_reported`'s arity,
  duplicating the test four lines above it. Replaced by two that drive a real
  `PieceMatcher` over two beliefs differing only in their candidates.
  `LoosePieceDetector._outline_of` moved onto `MatchedPiece.outline`. Thread replied to
  and resolved; PR description updated to match.
- 443 passed, 1 skipped, 4 xfailed against the parent's 423/1/5, collected sets diffed
  by name. `detect` at 1.08x the parent as a same-run ratio.
- Manifest saved to the successor plan; PR is a draft.

## Outstanding

- **CI is not read on this head.** The branch is deep in the fork stack; #222's
  `test_each_lib (krrood)` red is inherited by everything past it and is #251's to clear.
- Three things put to the developer on the PR rather than decided quietly: whether *equal
  cost* is the right thing to tell the robot for `required_lead`; that the cube on
  `tracy_pickup_demo` clears its runner-up by four parts in a thousand, so the operating
  range is narrow; and whether deriving the stated lead from the fits' own measurement is
  the reading he wants, given a clean drawn scene has a decisive winner.
- Landing hazards recorded on the PR: #223's `RectifiedFootprint` rename, #231's
  `EdgeFitDetector` rename, #255's `DetectedMontessoriShape` rename.

## Next

Nothing for this session. The item is built, the review round is answered, the PR is a
draft awaiting review, and the manifest matches the branch.
# competing-explanations (#270)

Plan item `competing-explanations` of `knowledge-directed-perception` (tracking issue
#201). Branch `claude/plan-item-kickoff-kdp-r8nttk`, stacked on #236, which carries #232.
Kicked off and built 2026-09-05 in `auto` mode. Full reasoning in the plan's `roadmap.md`
sections of the same name.

## Done

- Setup fixed (dashboard dependencies; branch re-cut off `main`, then onto #236).
- Context gathered; both dependencies `open_ready`; duplicate/purpose check clean.
- Branch cut, draft #270 opened, manifest and both roadmap sections saved, dashboard
  republished.
- **Built and pushed as `ee52352e0`.** `perception/explanations.py` (new) holds the
  two-sided account, the board's own outlines cast into a fit's own plane, and the
  comparison. `PieceMatcher.minimum_agreement` is gone and `match` is `fits`;
  `MontessoriShapeDetection` carries its `explanation`; `Occupancy` reads the same
  comparison instead of raw agreement.
- 442 passed, 1 skipped, 4 xfailed against the parent's 423/1/5 in the same container,
  collected sets diffed by name. `detect` at 1.08x the parent as a same-run ratio.
- `test_every_piece_resting_on_the_lid_is_found`'s `tracy_pickup_demo` mark reported
  itself stale and was removed. The other four are `expectations-from-events`'.
- PR description rewritten to match what the branch does.

## Outstanding

- **CI is not read on this head.** The branch is deep in the fork stack; #222's
  `test_each_lib (krrood)` red is inherited by everything past it and is #251's to clear.
- Two things put to the developer on the PR rather than decided quietly: whether *equal
  cost* is the right thing to tell the robot for `required_lead`, and that the cube on
  `tracy_pickup_demo` clears its runner-up by four parts in a thousand, so the operating
  range is narrow.
- Landing hazards recorded on the PR: #223's `RectifiedFootprint` rename, #231's
  `EdgeFitDetector` rename, #255's `DetectedMontessoriShape` rename.

## Next

Nothing for this session. The item is built, the PR is a draft awaiting review, and the
manifest, roadmap and dashboard all match the branch.
