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

### Round two of 2026-08-29: the developer's own pass

He resolved eleven of the thirteen threads himself. The two he left:

- **`hole_geometry.py:185`, "use a dataclass instead of the tuple"** — the
  `(area, centroid)` pair I had deliberately left as a plain two-value return
  last round. Now `PolygonMeasurement`, built by `PolygonMeasurement.of`
  (`33fe5a798`), with the shoelace formula's first direct tests.
- **`_SHAPE_COLORS`, "Is this file actually used in the tracy_icra demo? if not
  then I do not care about it for now."** — it is:
  `tracy_experiments/montessori/world.py` imports twenty-four names from
  `experiments/montessori/world.py`, `_SHAPE_COLORS` among them, and
  `TracyMontessoriWorld` is what both `montessori_demo_real.py` and
  `montessori_demo_mujoco.py` build. So the change was made (`7363d2c26`):
  `KnownPiece.color` answers what colour a piece is from its measured hue, and
  the scene asks.

**Cube and cylinder are now both cyan, and the two prisms both amber** — the
real set's colours, so two pairs share one each. Shape is what separates them
on the table and now in RViz. Only hue was ever measured, so the twin draws its
pure form; the assumption is stated on `KnownPiece.color`.

**147 passed, 1 skipped.** No review thread is open on the pull request.

### Next

- `surfaces-from-world` still needs to delete `pipeline.py`'s last read of
  `BOARD_SCALE` (for `BoardDetector.board_footprint`); `node.py` imports
  neither scene constant already.
- `detector-parameters-from-knowledge` now has a second reason to move the
  piece hues onto the objects: the twin reads them too, not only the detector.

### 2026-09-19: `test_each_lib (experiments)` deterministically red, unrelated to this PR's diff

Asked by the developer to "resolve PR 202 and fix the CI". The only red check
is `test_each_lib (experiments)`, failing identically across two prior CI
attempts (before this session touched anything) and a third I triggered to
rule out a flake: `sqlalchemy.exc.InvalidRequestError: Table already
defined`, for `ServoGainsDAO` (from this PR's own new
`tracy_experiments/equipment.py`) *and*, independently,
`MutagenesisCausalQueryResultDAO_effects_association` (a pre-existing,
untouched causal-reasoning association table). Confirmed green on `main` at
this PR's exact base commit, so it's something this PR's larger/changed
class set exposes in the generated `experiments.orm.ormatic_interface`, not
a base-branch issue.

Per `AGENTS.md`'s explicit "avoid ormatic_interface.py, consult the
developer" rule, asked the developer how to proceed rather than guessing a
fix inside shared `krrood/ormatic` internals. They chose "add a debug CI
step to dump the generated file."

Pushed two temporary debug commits directly to this branch (re-drafted the
PR after each, per standing rule):
- `26c458c96` — uploads the generated `ormatic_interface.py` as a build
  artifact. Downloaded and inspected it: **each class is defined exactly
  once in the file** (`grep -c` confirms). This rules out "the generator
  writes duplicate content" and confirms the module is being
  imported/executed *twice within one process* — something no plain
  `import X` should ever do, since `sys.modules` caches it.
- `313b88f4b` — adds a second debug step (`if: inputs.lib == 'experiments'`,
  `continue-on-error: true`) that: (1) builds the ORM interfaces up front
  via `WORKSPACE_ORM_INTERFACES.regenerate()`, (2) probes
  `experiments.__path__` after inserting `cognitive_robot_abstract_machine`
  onto `sys.path` the way pytest's rootdir insertion would (checking whether
  the checkout's own `experiments/` project folder, which has no
  `__init__.py`, is shadowing the properly-installed package — read through
  `PathFinder`'s namespace-package rules and think it shouldn't, but wanted
  it verified live rather than trusted from reasoning), and re-imports
  `experiments.orm.ormatic_interface` twice in the same interpreter to
  confirm plain re-import is safe outside pytest, (3) runs a *serial*
  (`--collect-only`, no `-n auto`) collection of `test/experiments_test` to
  see whether the bug reproduces without xdist at all — narrows whether
  xdist's per-worker collection is involved or whether it's a plain
  double-import bug that would show up even in serial pytest.

Both debug commits' logs/artifacts uploaded as `experiments-ormatic-interface`
(now containing both the generated file and `/tmp/serial_collect.log`).
**Debug scaffolding must be removed from `ci_reusable.yml` once the real
fix lands** — do not let it merge as-is.

Next: read the run-`313b88f4b` artifact/logs once CI finishes, decide from
the serial-vs-xdist result and the sys.path probe output what's actually
double-importing the module, then push the real fix (likely somewhere in
how the pytest process resolves `experiments.orm.ormatic_interface` the
first time vs. the second, not in generator content) and revert the debug
step. The developer said "Check it" and expects a report once this run
completes; per standing rules I'm not polling — checked this once and will
check again when prompted.
