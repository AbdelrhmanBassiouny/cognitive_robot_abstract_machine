
## PR #292 — RecordedLook ORM collision

**What this is.** The last red job on #265 (`test_each_lib (experiments)`,
13 failed / 8 errors) was one name collision: two dataclasses in
`experiments.montessori.perception` both called `RecordedLook`, so the
generator emitted `RecordedLookDAO` twice, SQLAlchemy refused the second,
and every later import of the half-executed module collided on the first
association table it had registered.

**Decision.** Rename, not `ignored_classes`. Ignoring the bag-reading family
would have to grow to cover `watch_bag` (BagReplay holds a `RecordedCamera`)
and every later holder of one, leaving the duplicate name in place for the
next class to hit. Rename follows #223's `Footprint` -> `RectifiedFootprint`
precedent and is the only option verifiable without ROS.

**Naming.** `recordings.py`'s becomes `RecordedImages` (+ `RecordedCamera.
images()`/`image_at()`); `step_by_step.py` keeps `RecordedLook`. Note
`RecordedFrame` was the obvious name and is already taken by
`scene_source.py`.

**Base.** Cut from and targeted at `claude/icra-experiments-simulation-
pipeline-w4ep7n`, not `main`: `git ls-tree main` is empty for both perception
files, so the two only meet on #265. This is a change to that PR, not
standalone work — the scope check in the notes says fold rather than stack.

**Done.** Failing test added first (`test_montessori_orm.py`:
no two mapped Montessori classes share a name with each other), rename +
three readers updated, docstrings formatted, committed, pushed, draft PR #292
opened with the `bug` label.

**Next.** CI run 34059721576 is the only proof — nothing here can run the
experiments ORM generation. If `test_each_lib (experiments)` is green, the
item's third blocker in `icra-foundation/plan.yaml` clears and should be
struck; the four narrowing-test failures remain a separate blocker and are
untouched by this. If still red, read the job log before assuming the rename
is at fault — the new collision test may have surfaced a second duplicate
name the generator never reached before.

