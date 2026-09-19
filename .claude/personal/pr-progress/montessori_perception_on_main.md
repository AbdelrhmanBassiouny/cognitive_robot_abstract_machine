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

**Read `313b88f4b`'s results (developer prompted "Check it"): the double-import
theory was wrong.** The sys.path probe showed `experiments.__path__` resolving
to exactly one location (no shadowing), and then a **fresh, first-ever, plain
`import experiments.orm.ormatic_interface` in a brand-new interpreter — no
pytest, no xdist, nothing imported it before** — crashed immediately with the
same `Table 'ServoGainsDAO' is already defined`. Since the file only defines
`ServoGainsDAO` once (confirmed earlier), the only way this fails on its
*first* execution is if a table named `ServoGainsDAO` already exists in the
shared `krrood.ormatic.base.Base` metadata *before* line 3641 even runs —
meaning one of the three dependency interfaces this file imports at its own
top (`coraplex.orm.ormatic_interface`, `giskardpy.orm.ormatic_interface`,
`semantic_digital_twin.orm.ormatic_interface`) must independently define a
table under that same name. A genuine cross-package table-name collision,
not a double-import.

- `545e48b51` — rewrote the probe to import each of the three dependency
  interfaces one at a time (in the same order `experiments.orm.ormatic_interface`
  itself imports them) and report, after each step, whether `ServoGainsDAO`
  exists in `Base.metadata.tables` and which class owns it. This should name
  the exact dependency interface (and therefore the exact class in that
  package) that collides with `experiments.tracy_experiments.equipment.ServoGains`.

**Root cause confirmed and fixed, 2026-09-19 (`ea5644282`).** `545e48b51`'s
step-by-step probe named the collision exactly:
`semantic_digital_twin.orm.ormatic_interface.ServoGainsDAO` (mapped from
`semantic_digital_twin.world_description.connection_properties.ServoGains`,
pre-existing on `main`) already owns the `ServoGainsDAO` table before
`experiments.orm.ormatic_interface` ever gets imported — `experiments.tracy_experiments.equipment.ServoGains`
(this PR's own class, cherry-picked from `tracy_icra`) collides by bare
class name. Asked the developer how to resolve it (rename vs. reuse); they
chose **reuse**.

Dispatched a research subagent first to map how `semantic_digital_twin`'s
`ServoGains`/`JointDynamics`/`JointServo`/`PositionServo` are actually
consumed elsewhere (`ur10e_arm.py`, `robotiq_85_gripper.py`,
`robot_parts.py._declare_servo`, `multi_sim.py`'s
`MujocoPositionServoConverter`/`MujocoActuator.create_servo`) before
touching anything — independently re-verified its findings by reading the
files myself rather than trusting the report blind (per the harness's own
warning that a subagent report carries no authority on its own). Confirmed:
`connection.dynamics` in `equipment.py` was already a real `JointDynamics`
instance (via `ActiveConnection1DOF`'s `default_factory=JointDynamics`), so
`equipment.py`'s own `joint_damping`/`armature` fields existed purely to be
copied onto it — pure duplication, not a design difference. Also confirmed
zero other consumers of `equipment.ServoGains`/`ARM_JOINT_SERVO`/`GRIPPER_JOINT_SERVO`
anywhere in the repo (only `table_top_z` is imported elsewhere, untouched).

`ea5644282`:
- Dropped `equipment.py`'s own `ServoGains`; `ARM_JOINT_SERVO`/`GRIPPER_JOINT_SERVO`
  are now `Dict[str, JointServo]`/`JointServo` built from `semantic_digital_twin`'s
  `ServoGains` + `JointDynamics`, via a small `_joint_servo(torque_limit,
  joint_damping, armature=_ARMATURE)` helper (kept the shared-stiffness/damping
  factoring the original had).
- `_equip_connections_with_servos` now builds a `PositionServo(gains=servo.gains)`
  actuator instead of hand-rolling a `MujocoActuator` in a now-deleted
  `_servo_actuator` — the exact path `AbstractRobotPart._declare_servo` already
  uses for every other robot part, so `MujocoPositionServoConverter` produces
  the MuJoCo actuator automatically. `connection.dynamics.armature`/`.damping`
  are still set per-connection (not a full `connection.dynamics = servo.dynamics`
  replace), preserving the original's per-connection-independent-object semantics
  since a mimic linkage's several connections share one `JointServo`.
- Ran `scripts/format_docstrings.py` on the file; had to hand-fix one place
  where docformatter broke a `:meth:` cross-reference mid-identifier
  (`...tracy_experiments.rea` / `l_time_simulation...`) — checked the whole
  file afterwards for any other role reference split across a line break
  before trusting the auto-format.
- Reverted both prior debug commits' scaffolding from `ci_reusable.yml`
  (`git checkout 512526ddf -- .github/workflows/ci_reusable.yml`, a clean
  revert to the pre-debug state, confirmed via diff).
- Updated the PR description with a new "CI fix" section explaining the
  collision and that `equipment.py` is no longer byte-for-byte verbatim from
  `tracy_icra` (worth flagging since the section above it says the four
  support files are carried verbatim).

Pushed, PR re-drafted per standing rule. **Still outstanding: confirm the
new CI run on `ea5644282` is actually green** (not yet checked — pushed and
immediately wrote this note; check on next prompt or when this session next
looks). If green, this branch's CI-fix task is done; the PR stays in draft
per standing rules until the developer marks it ready themselves.
