# expectations-from-events (#257, draft) - knowledge-directed-perception

Kicked off 2026-09-03 in `auto` mode. Branch
`claude/plan-item-kickoff-expectations-2zvpmn`, cut from #232
(`claude/plan-item-kickoff-kdp-o4l189`). Full reasoning is in the plan's
`roadmap.md` section of the same name; this note is the working state.

## The base, and why

Three dependencies on three stacks. Base #232 (the believed place is defined
there), merge #222 in (SceneRequest, how an expectation reaches a look) and
#246 in (the events, and #244 under it which removes the geometry_msgs import
that stops segmind collecting without ROS 2). Basing on #238 would have cost
one merge instead of two and was refused: it carries 6,853 lines of another
item's diff into this review.

Measured: #246 into #232 clean; #222 into #232 five hunks in `pipeline.py` and
`test_montessori_perception.py`, the merge #238 already recorded as resolving
as a union.

## Plan

1. Merge #222, then #246, into the branch. Resolve the two files as a union,
   reading #238's recorded resolution rather than re-deriving it.
2. Tests first for `perception/expectations.py`: `Expectation` (a named piece
   at a `BelievedPlace`, and what put it there), `ExpectedPlaces` (the store,
   propagated by the three rules), the violated-part report.
3. Build it. Three propagation rules from the item's notes: released over a
   hole -> believed at that hole, any turn, within the release spread; still
   grasped -> the gripper's pose; acted on by nothing -> where it was last
   seen. Segmind's five events confirm or refute.
4. `SceneRequest` carries what is expected; `pipeline.detect` evaluates it
   beside `expected_pieces()`.
5. The captures: state the insertion's declared effect in `recorded_setup` for
   the three cube-at-a-hole captures, and measure which of #232's four lid
   expected-to-fail marks come off. Whether all four do is a measurement, not
   a promise.
6. `scripts/format_docstrings.py` over every touched file; run the suite and
   compare failing sets by name, not by count.

## Done

- Branch cut from #232's tip, bootstrap commit pushed.
- Draft #257 opened, manifest recorded (`in_progress`, branch, PR, session),
  roadmap section written, plan saved to personal-notes (`7ca44d498`).

## Next

Step 1 - the two merges.

## Watch out

- `plan_item_bootstrap.py open` fails here (four-space `ITEM_FIELD_INDENT`
  against this plan's two-space item fields, error swallowed by
  `capture_output=True`); the manifest was edited directly. Sixth time.
- The tracking-issue subscription was refused by the permission classifier, so
  read #201's comments directly before any later round. Doing so at kickoff is
  what turned up `icra-experiments`' 2026-09-03 cross-plan record, which this
  plan's roadmap did not carry: this item is the one thing that plan still
  needs and the only critical-path item with no branch.
- #255 (kicked off the same day) renames `MontessoriShapeDetection` to
  `DetectedMontessoriShape` across `pipeline.py`, `detections.py` and
  `occupancy.py`. This branch edits `pipeline.py`, so it inherits it.
- `InsertMontessoriShapeAction` is on `tracy_icra` only; the declared effect is
  a rule this item owns and the action calls, not an edit to the action.
- Open and stated on the PR rather than decided silently: whether the belief
  store belongs in `experiments` or generally in krrood/sdt. Review overturned
  that placement twice on #222.
