# #296 (icra-foundation / montessori-scenarios) - fifth review round, 2026-09-09

## The plan
One unresolved thread was left on #296, asking where the demo's actuation should
live and how the scenarios reach the demo; the answer arrived as "do (1)" at
07:16 UTC on 2026-09-09. Option (1) is: open the one seam that is still closed -
a scenario is built on the scene it is given rather than building a
`MontessoriWorld` of its own - and leave `tracy_icra`'s 1,200 lines of actuation
where they are, for `tracy-demo-takes-the-integrated-branch` to bring together.

## Done
- `MontessoriWorldBuilder` (abstract) and `BoardOnItsOwnTable` (this package's own
  scene) in `montessori/scenarios.py`; `MountedRobot` moved onto the latter, since
  where a robot is bolted is part of setting a scene up and a demo computes it
  from its own robot rather than stating it.
- `MontessoriSortingScenario.robot` -> `world_builder`; `build_world` asks the
  builder for a scene per trial; the piece resting height and the pusher's rail
  now read the given scene's table top rather than the module constant.
- Three tests written first, each mutation-checked: the scenario runs in the scene
  its builder built, stands its pieces on that scene's table, and bolts its robot
  where that scene says.

## Next
- Reply on the thread and resolve it; update the pull request description.
- Record the round in the plan's roadmap and item notes, then republish the
  dashboard.
- Left as it was: the layout's own geometry (`LayoutArea`,
  `PiecePlacement.standing_height`) is still measured against this module's
  `TABLE_TOP_Z`, so a scene on another table also needs its layout stated in that
  frame. Named on the thread rather than built unasked.
