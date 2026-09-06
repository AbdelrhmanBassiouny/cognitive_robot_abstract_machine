
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

