
# #265 - icra-foundation / integrated-simulation-pipeline

Getting CI green, after /plan-item-resolve got the generation running.

## Where it stands

CI collected for the first time on f5c383a8: thirteen of fifteen jobs green,
`Examples and Demos` green in full. The two that failed were one defect each,
both this branch's own, both now fixed and pushed as e6c665ce.

## Done

- **The generated experiments interface would not import.** A relationship was
  rendered with the container its field declares, and `SurfacePass` declares the
  abstract `Sequence`, so the module named `collections.abc.Sequence` without
  importing it - which SQLAlchemy could not have instrumented anyway. A
  relationship is now held in a collection SQLAlchemy can build and append to,
  as the tuple case already was. The `Table '_5187...' is already defined`
  cascade was the same defect's second half: the NameError left a half-executed
  module behind. Nine failures and six collection errors, one cause.
  Reproduced first as a krrood test over three classes and no ROS.
- **`InsideOf.compute_containment_ratio`** was kept in its older
  mesh-and-bounding-box form over 01e454d7b's numeric one - alone among that
  commit's numeric readings - against the test asserting containment builds
  nothing symbolic. Restored. Three containment tests pass now, two of them for
  the first time in this container.
- PR description updated (the two defects, the new verification, and a rewritten
  "Left for the developer"). Manifest blocker, item note, roadmap sections and a
  standing hazard recorded.

## Next - the developer's call, not mine

The four tests in `test_montessori_search_narrowing.py`. Bisected: all 27 pass
at 16c483635, the same four fail at 03d9719d9, the merge of the hole layout fit
(#236), which moves the board 40 mm along y on `tracy_pickup_demo`. The picture
settles which fit is right - #236's hole centres land on the six real openings,
the pre-#236 centres on bare wood - so the code is right and the measurements
are stale. But re-measuring is not enough: the cube is 50.3 mm from the square
hole and the cylinder 51.6 mm, so no radius separates them, and the cylinder is
5 mm to that hole's left rather than its right. Two of the four need a different
hole or a different pair to keep demonstrating what they were written for.

Also still open and untouched: the unbounded `SimulationTimePacer.sleep()`, and
whether `EdgeFitDetector`/`ColorBlobDetector` collapse into one.

The PR is ready-for-review (not a draft) - the developer flipped it, so it was
left that way rather than re-drafted after this push.

