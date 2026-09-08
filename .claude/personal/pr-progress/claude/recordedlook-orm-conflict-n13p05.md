
## PR #292 — two root causes of `test_each_lib (experiments)` — pushed, CI running

### 1. The duplicate `RecordedLook` (76e37a70) — done, CI-proven

Two dataclasses in `experiments.montessori.perception` both called
`RecordedLook`, so the generator emitted `RecordedLookDAO` twice, SQLAlchemy
refused the second, and every later import of the half-executed module
collided on the first association table it had registered. Renamed
`recordings.py`'s to `RecordedImages` (`looks()`/`look_at()` ->
`images()`/`image_at()`) rather than extending `ignored_classes`, which would
have had to grow over `watch_bag` and every later holder of a
`RecordedCamera`. CI: parent `e6c665cec` 13 failed / 8 errors / 51 mentions of
the duplicated table; `76e37a70` 4 failed / 758 passed / 0 errors / 0 mentions.

### 2. Hole bodies 12 mm from the hole the look found (73b0c1cb) — the four narrowing tests

`board_holes_in` added the board mesh's own **unscaled** hole offsets to the
fitted board pose. Since #236 the board is found at
`BOARD_SCALE_AGAINST_THE_MESH` = 0.865, so the bodies stood 12.1 mm (square
hole) and 12.7 mm (disk hole) from the detections. Every direction and
distance a statement reads from a hole was read from a place 12 mm off.
Fixed by placing each hole where the look put it; `hole_names` now takes
categories so a detection can be named by it. New test
`test_montessori_recorded_setup.py::test_a_hole_body_stands_where_the_look_found_that_hole`
fails on the parent at those two distances.

### The reconciliation with `dae41889c`, on #265

While this branch was working, #265 landed `dae41889c`, which read the same
four failures as stale docstrings and restated them. Its premise measured the
displaced bodies: the hole y values it quotes (0.0182 … 0.1968) are the
displaced ones; placed where the look found them the six stand at 0.0299 …
0.1845, so the square hole *does* lie between the cylinder (0.0231) and the
cube (0.0634), and the 1.3 mm that ruled the square hole out of the reach test
was the displacement.

**It is kept, not reverted** — all four of its choices still hold once the
holes move, and two read better than the originals. `8b8914c74` requotes the
millimetres (19→21, 45→43, 16→19, 49→47, 50 and 94→51 and 93, 25→27, 39→37)
and replaces the one claim that does not survive: `look_for_the_cube_on_the_lid`
said left and right tell the two pieces apart from no hole on this board.

### How it was checked — the container hazard is wrong again

`pytest` runs here. A python3.12 venv (workspace sources on the path,
`random_events`/`probabilistic_model` wheels, `casadi~=3.7.0`, `objgraph`,
`pytest>=7,<8`) plus **`CRAM_ORM_BUILD=never`** to skip the conftest's ORM
generation: `test_montessori_search_narrowing.py` runs in 75 s, 28 passed;
506 passed across the montessori suite. The 15 that fail are
`test_montessori_orm.py` and `test_montessori_results_database.py` (need the
generated interfaces and a database) and fail identically with the change
stashed. So the four narrowing failures were reproduced locally *before* the
fix and driven green after it — the first time this branch had a real loop.

### State

Pushed `8b8914c74`. PR description rewritten to cover both causes and the
reconciliation. Plan manifest + roadmap updated (personal-notes `3b799abc9`),
dashboard republished. The PR is **not a draft** — the developer took it out
of draft himself, so it is left ready.

**Outstanding:** CI on `8b8914c74` had not reported when this was written.
Nothing else known red. No subscription armed, no check scheduled.


## PR #292 — RecordedLook ORM collision — DONE, CI-proven

**What it was.** The last red job on #265 was one name collision: two
dataclasses in `experiments.montessori.perception` both called `RecordedLook`,
so the generator emitted `RecordedLookDAO` twice, SQLAlchemy refused the
second, and every later import of the half-executed module collided on the
first association table it had registered.

**Decision: rename, not `ignored_classes`.** Ignoring the bag-reading family
would have to grow over `watch_bag` (BagReplay holds a `RecordedCamera`) and
every later holder of one, leaving the duplicate name for the next class to
hit. Rename follows #223's `Footprint` -> `RectifiedFootprint`, and is the
only option checkable without ROS.

**Naming.** `recordings.py`'s -> `RecordedImages`; `looks()`/`look_at()` ->
`images()`/`image_at()`; `step_by_step.py` keeps `RecordedLook`.
`RecordedFrame` is already `scene_source.py`'s — worth knowing before naming
anything else in that namespace.

**CI result (the only proof; nothing local can run this).**
- parent `e6c665cec`, run 34053623592: 13 failed, 742 passed, 8 errors, 51 log
  mentions of the duplicated table.
- #292 `76e37a70`, run 34059721576: 4 failed, 758 passed, 0 errors, 0 mentions.
- New test `test_no_two_montessori_classes_share_their_name_with_each_other`
  collected and PASSED. 14/15 jobs green.

**Still red, and deliberately not mine.** The four
`test_montessori_search_narrowing.py` failures fail identically on the parent
and are `icra-foundation`'s separate blocker — a design call about the
perception story (no radius separates cube from cylinder against #236's
corrected layout; the cylinder is left of the square hole, not right).
Standing-down comment posted on #292.

**Plan state updated.** Collision blocker struck from
`icra-foundation/plan.yaml`; rationale + measurements in `roadmap.md`; the
`Footprint` standing hazard generalised to any reused bare class name in
either direction. Saved at personal-notes `7894cae2`.

**Next — nothing for this session.** #292 is a draft awaiting the developer.
If it is folded into #265 rather than merged, the four narrowing tests are what
remains between #265 and green. No subscription armed, no check scheduled.

