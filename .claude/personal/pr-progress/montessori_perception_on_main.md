## Branch `montessori_perception_on_main` — PR #202

Plan item `montessori-perception-on-main` of `knowledge-directed-perception`
(tracking issue #201). Opened **ready for review, not draft**, at the
developer's explicit decision — see "Why not a draft" below. Nothing is
merged; `main` is untouched.

### Plan (settled 2026-08-28, `auto` mode with two decisions put to the user)
Cut the perception package off `tracy_icra` as a reviewable branch off `main`,
so wave 1's items stack on reviewable ground. Two questions went to the
developer because they changed the item's recorded scope; both were answered
with the recommendation:

1. **Scope** — carry the four support files the package needs *plus their
   existing tests*, rather than narrowing or inlining. It is the only shape
   that actually imports.
2. **Pull request state** — ready for review, not draft, so the dependents
   stop reading as blocked.

### Done
- `b5d0745e` — the four support files (`semantics.py`, `hole_geometry.py`,
  `world.py`, `equipment.py`) and their three tests, verbatim from
  `tracy_icra`, authored to sorinar329 who wrote them.
- `714efc6a`..`57dd97cd` — the eight perception commits cherry-picked in
  order, sorinar329's authorship preserved on the first, hunks touching
  `montessori_demo.py` and `tracy_experiments/montessori/world.py` dropped.
- `256fe58b` — `resources/board.stl`, which `hole_geometry.py` loads at import
  time. A module-only closure check never sees it.
- `ac2fb7e1` — the synthetic robot fixture and URDF `test_montessori_world.py`
  builds its scene on.
- `13b0374f` — declares `opencv` in `experiments/pyproject.toml`. The package
  imports `cv2` in six modules and it was never declared.

34 files, 9,664 insertions, zero deletions. **140 passed, 1 skipped.**

### Why not a draft
`build_dashboard.py`'s `is_ready_to_unblock_dependents()` counts a dependency
ready only when done, merged, or *open and out of draft*. A draft here would
have left `surfaces-from-world` and `perception-backend` blocked with no
"Start now" button — the exact symptom that prompted this item. Per personal
notes, a session marking its own pull request ready to unblock a dependent is
not the signal that its job on that pull request has ended, so re-draft after
any future push as usual.

### Next
- `surfaces-from-world` stacks on this branch. When it runs, it should
  *delete* this branch's two thinnest dependencies: `BOARD_SCALE` from
  `montessori/world.py` and `table_top_z` from `tracy_experiments/equipment.py`
  are precisely what it replaces with world-derived values. That deletion is a
  checkable outcome of that item, not incidental cleanup.

### Watch out for
- The ORM path is unexercised. The repository conftest regenerates the ORM
  interfaces on collection, which imports `giskardpy` and needs ROS 2; the
  tests above were run with `--noconftest` and the workspace on `PYTHONPATH`.
  The same failure reproduces on unmodified `main` in this container.
- CI has not been seen yet — the branch was pushed and the pull request opened
  in the same turn.
