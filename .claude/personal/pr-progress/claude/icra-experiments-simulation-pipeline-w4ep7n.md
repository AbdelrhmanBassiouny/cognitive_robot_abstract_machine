## `/plan-item-resolve icra-foundation integrated-simulation-pipeline` - the four narrowing tests

**Done, pushed as `dae41889c` on #265's branch
`claude/icra-experiments-simulation-pipeline-w4ep7n`** (approved in session; this
session's own designated branch descends from `integration` and is unusable as a base,
and the scope check leaves the touched files on no other base either).

**What the resolution turned on.** Measured over all six holes rather than the square
one, left and right separate the cube from the cylinder from no hole on this board, read
from the camera or from the world - no hole's y lies between them. Only front-back in
the world and up-down in the picture do, and every hole affords both. That single fact
chose all four changes, and corrected the recorded blocker: three tests read a
left-right direction, not two, and the fourth was the production statement rather than a
test.

- `..._reaches_as_far_as_the_radius_it_was_asked_for` -> triangle hole, radii 0.07/0.12
  (cube 50.0 mm, cylinder 93.8 mm). Not 0.05: the cube stands at 50.04 mm.
- `test_the_two_sides_of_a_hole_hold_different_pieces` -> `InFrontOf`/`Behind` on the
  square hole (16.2 mm in front, 49.1 mm behind). One axis, where the old pair crossed two.
- `test_which_way_a_piece_lies_from_a_hole_is_read_from_where_it_is_seen` -> `RightOf`
  becomes `Below` (cube 18.6 mm up the picture, cylinder 45.4 mm down).
- `test_the_demonstration_states_its_way_down_to_the_cube_alone` -> no test edit;
  `watch_narrowing.look_for_the_cube_on_the_lid`'s `LeftOf(square_hole)` becomes
  `Above(square_hole)`.

All four verified end to end through `MontessoriPerceptionBackend` (9/9 checks), plus the
sibling invariants over the demonstration statement: areas 0.517 > 0.041 > 0.023, five
distinct labels of non-decreasing length, the camera named exactly twice.

**Recorded.** Blocker cleared and the outcome written into the item's notes plus a
roadmap section; dashboard republished at
https://claude.ai/code/artifact/26aa1240-a91c-440b-ab3a-24f59156ea62 . #265 converted
back to draft and its description rewritten (the "Left for the developer" section had
gone stale).

**Outstanding on #265, neither of them this work's and neither actioned:**
1. **Merge conflict against `main`**, 4 files - `mapped_variable.py`, `world.py`,
   `geometry.py`, `test_color.py`. Exactly the four #296's roadmap section predicted, and
   it warns of a silent breakage behind them (`memoize` moved from `krrood.utils` to
   `krrood.patterns.caching`, which #265's `world.py` still imports the old spelling of).
   Pre-existing; resolving it is convergence work, not this item's.
2. **The experiments job stays red** until #292 lands - the duplicate `RecordedLook`.
   #292 is an open draft cut from this branch and targeted at it; its `76e37a70` ran
   4 failed / 758 passed, and those four were these tests. So #292 + `dae41889c` is what
   takes the job green.

**Environment note worth keeping.** The roadmap's standing "nothing on these branches
runs in a session container" is wrong for the montessori perception suite: a python3.12
venv with the workspace sources, `random_events` editable and `casadi~=3.7.0` (3.8 breaks
`FunctionBuffer.set_res`) runs the whole pipeline. Only `pytest` is blocked, in the
conftest's ORM generation (`CouldNotResolveType: QPControllerConfig`, walking giskardpy),
so the behaviours were driven from a script mirroring the test bodies.
