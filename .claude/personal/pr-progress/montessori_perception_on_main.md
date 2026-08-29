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

### Round of 2026-08-29: the test split, and the review

`00721be7` split `test_montessori_perception.py` (1262 lines) into six modules,
one per subject, with the four shared fixtures moved to
`dataset/montessori_scene_fixtures.py` and registered through `pytest_plugins`.
That work was `surfaces-from-world`'s review comment, placed here by the
developer because the file arrives with this branch.

The developer then reviewed the branch itself: thirteen threads. Four asked for
a change here, and each is one commit:

- `bb37390d` — `NoMatchingHoleError` moves to
  `experiments/montessori/exceptions.py`. Its raise had no test; writing one
  found that both existing board tests pass a `PrefixedName` where
  `create_with_new_body_in_world` takes a `str`, which double-wraps the name and
  makes the error's own message raise `TypeError`. The new test passes a plain
  string; the existing tests were left alone.
- `3348e353` — `HoleFootprint`'s centre, size and boundary points become
  `PlanarPoint` / `PlanarSize`. `semantic_digital_twin`'s `Point2` was
  considered and rejected: it is a casadi symbolic point with a reference
  frame, and these are plain metres in the mesh's local frame.
- `be8b8514` — the perception package's `__init__.py` is empty.
- `a9204f5e` — the node's poll interval is `scene_check_period`, a field.

**142 passed, 1 skipped**, against 140 before.

The other nine threads are one ask — the detectors' numbers are knowledge about
the pieces, surfaces and lighting — and the developer directed them into plan
items, not into this pull request. They became
`detector-parameters-from-knowledge` and (deferred)
`tune-detection-rules-against-the-camera`.

### Next

- `surfaces-from-world` stacks on this branch and should delete this branch's
  two thinnest dependencies, `BOARD_SCALE` and `table_top_z`. Partly done there
  already: `node.py` imports neither, but `pipeline.py` still reads
  `BOARD_SCALE` for `BoardDetector.board_footprint`.
- Seven review threads are deliberately left open for the developer, each
  replied to with where its ask went. One of them, `_SHAPE_COLORS` in
  `world.py`, has a small change waiting on his answer: whether the simulated
  world should render the real set's colours now, or wait for the knowledge to
  move onto the pieces.

### Watch out for

- The ORM path is unexercised: the repository conftest regenerates the ORM
  interfaces on collection, which imports `giskardpy` and needs ROS 2. Tests are
  run with `--noconftest` and the workspace on `PYTHONPATH`; the same failure
  reproduces on unmodified `main` in this container.
- `node.py` cannot be tested here at all — it imports `rclpy`, which no
  environment in this workspace has, so no test covers `scene_check_period`.
- CI was green on all 23 checks before this round's push.
