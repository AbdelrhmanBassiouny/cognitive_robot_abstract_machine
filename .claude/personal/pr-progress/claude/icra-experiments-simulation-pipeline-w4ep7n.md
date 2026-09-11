## #265: live shape and hole detection is wrong on the new 80 % pieces (2026-09-11, in progress)

**Session.** https://claude.ai/code/session_0186xZo3eqCDVcqhi1E3LHdY -- resume here if
anything breaks. Memory note `perception-position-offset-stopgap` holds the earlier
diagnosis (live detections ~0.3 m toward the camera; extrinsics/intrinsics/frame_id/
table height ruled out; stopgap only on `icra_final`).

**The task, in the developer's words (2026-09-11).** "We working on fixing the perception
detection of the shapes issue ... the sample images I showed you where the detections are
wrong, the objects btw are new they are scaled down to 80 % so for example the cube side
length is now 22.4 mm instead of 30 mm. Also the ground truth positions of the current
situation is as follows all at the same x value of 79 cm while the y values are (cylinder
10 cm, triangle 20 cm, rectangle 30 cm, cube 40 cm). We want to take captures now and
save them with tests that compare against the ground truth. The board front left corner
is at (99, 40) cm where the side with the drawers and handles are toward the shapes and
it is fairly horizontal along the y axis (same x value in each horizontal (long) side).
We need to find the issue in the hole detections and the shape detections and fix them.
Also save this prompt here in the repo and add this conversation and session in the
history so I can resume later if something happens."

**Ground truth of the table as set up on 2026-09-11** (reference frame, metres):
pieces all at x = 0.79: cylinder y = 0.10, triangular prism y = 0.20, rectangular prism
y = 0.30, cube y = 0.40. Board front-left corner at (0.99, 0.40); the drawers-and-handles
side faces the pieces; long sides run along y at one x each. Pieces are the new set at
0.8 of the measured ones (cube 22.4 mm instead of 30 mm).

**What the two screenshots (17:46, 17:55) show.** The board box is found, but the hole
labels (`cube`, `cylinder`, `disk`, `triangular_prism`) sit on the wrong holes and only
four or so holes are boxed; of the pieces on the table only the triangular prism is
detected (green), the cyan cube and yellow rectangular prism get no box at all.

**Uncommitted at session start** (files 18:24): `perception/live_camera.py` (`LiveCamera`,
`CameraPoseLookup`) and `perception/capture_from_camera.py` (CLI writing one live look as
a `SceneCapture`). `node.py` still has its own duplicate subscriptions/`TFWrapper`. No
tests for either yet. No new capture written yet.

**Found 2026-09-11 evening (root cause).** The published `table -> camera_link` transform
(`iai_tracy_description/urdf/tracy.urdf.xacro`, commit `db06ecf` of 2026-04-30, "new
calibration for camera_link", xyz `0.410542 -0.015143 0.932933` rpy `-0.046277 1.378820
-0.050299`) is stale: the camera has physically moved since. Measured off the depth of
*every* shipped capture and the new one alike: the table's normal is 22.9-23.0 deg off
the optical axis (published: 11.0 deg) and the camera stands 0.892-0.894 m above the
table (published 0.935). Projecting the robot's own gripper (TF `l_gripper_tool_frame`)
into the picture with the published pose lands ~240 px above the real fingers; with the
fitted pose it lands on them. Fitted pose in `map` (optical frame, 4x4) is saved in the
scratchpad as `T_new.npy`; as a `camera_link` origin in the `table` frame it is
xyz `0.4264 -0.0206 0.8938` rpy `0.0400 1.1716 0.0326` (tilt+height from the table plane,
x/y from the gripper pixel, yaw kept from the URDF). *The URDF must be recalibrated; that
is outside this repo.* With the fitted pose: the pieces deproject to x 0.788-0.793 and
y 0.014/0.111/0.209/0.305 against the tape's 0.79 and 0/0.10/0.20/0.30 (corrected by the
developer: cylinder 0, triangle 0.10, rectangle 0.20, cube 0.30; board front-left corner
(0.99, 0.30)); the board is found at x 0.986-1.100, y 0.021-0.305 with the mesh at scale
1.0 and all six holes on their openings. `BOARD_SCALE_AGAINST_THE_MESH = 0.865` is an
artefact: the wrong tilt reads the board at 0.81 (x) x 0.92 (y) of its size, mean 0.865.
The tuned workspace (`tracy_workspace.json`, max x 0.915) also excludes the true board.
The new pieces are 0.8 of the old set (cube 22.4 per the developer; cylinder 22.4,
rectangle 16x32, triangle side 29.6, ~24 tall) and a different colour: hue 98 (was 86,
cyan) and 26 (was 21; note 26 is also the board's wood). With pose + scale 1.0 + a 0.8
set with those hues, all four pieces are detected within 1 cm of the tape.

**Plan.**
1. Finish `LiveCamera`: `MontessoriPerceptionNode` reads through it; mocked tests for
   `LiveCamera`/`write_capture`. Commit.
2. Take captures off the live camera with `capture_from_camera.py`, ship them under
   `resources/captures/`.
3. Table-plane fit module + a test that every capture's depth agrees with its stated
   pose (fails today); rewrite all seven captures' `reference_frame_T_camera` to the
   fitted pose.
4. Board mesh at its own size (drop 0.865); workspace re-tuned to reach the board.
5. A known-piece *set* the pipeline is handed (old set for the shipped captures, the
   0.8 set with its hues for the new capture and the live node).
6. `CaptureTruth` with positions; ground-truth tests on `scaled_pieces_in_a_row`.
7. Re-run the whole montessori suite; re-measure whatever the corrected pose moves.
8. Update this note and the PR description; push; keep #265 a draft. Tell the developer
   the URDF numbers.

## #265: the board is found by describing it in EQL (2026-09-11)

**State.** `040e2daa7` on `claude/icra-experiments-simulation-pipeline-w4ep7n`, pushed to
`bass` (with `~/.ssh/id_ed25519_bass`, now pinned as `remote.bass.sshCommand`) and to
`sorin`. Still a draft. PR description **not** updated -- no `gh`/token on this machine.

**What.** `9ab372901` brings the ShapeSortingBoard fix over from `icra_final`'s
`c3c5962c5` on its own: `node.py` died on `BoardMissingFromWorld` when the live world
held no board. Now `DescribedBoard.statement()` is a `Match` over `ShapeSortingBoard`
(lid_size, height, apertures of `ShapeSortingHole` with shape/size/place/turn on the
lid); `MontessoriPerceptionBackend.read_request` reads it back as a `DescribedBoard`, the
look fits that layout at `table height + stated height`, stands the board found in the
look's world, and the match answers with it. `node.hold_board` publishes it into the
robot's world via `BoardPublisher` and re-reads the lid. That `icra_final` commit was
itself broken -- it imported `board_description.py`/`board_publishing.py` which were
never committed (they sat untracked in this working tree); both are in now. Left out of
that commit deliberately: the `LIVE_POSITION_CORRECTION` stopgap, the `world.py` piece
scaling (+ untracked `test_montessori_shape_bodies.py`), coraplex/tracy_experiments
changes. Two tidy-ups over `icra_final`: `stand_in` takes the lid `Pose`;
`ShapeSortingBoard.held_by(world)` replaces three copies of the lookup.

**Verified.** `test/experiments_test -k montessori`: 735 passed (only the untracked
scaling test fails); `node.py` starts against the live robot and reports 6 holes.
`040e2daa7` merges #303 (krrood backend `capability()`), which does not touch the
perception backend (`GenerativeBackend` implements it).

**Outstanding.** PR description needs the paragraph above. The live ~0.2-0.3 m position
offset is uncorrected on this branch (stopgap stays on `icra_final`, root cause open).
Untracked leftovers: `pickup_demo_perceived_board.py` + test, the `.mcap` bag dir,
`ganttchart.pdf`, `.mcp.json`.

## #265: tracy_icra merged, LongTermMemory CI fix, main merged a second time

**State.** `51fc40548` on `claude/icra-experiments-simulation-pipeline-w4ep7n`, a draft,
description up to date (PR body's new section covers this round). Pushed.

**What happened, in order.**

1. `c719c44a9` merges `tracy_icra` in, at the developer's request, ahead of
   `tracy-demo-takes-the-integrated-branch`. Eleven conflicted files in `segmind`'s
   detectors and `coraplex/execution_environment.py`, all resolved by reading both
   sides rather than picking one. Found and fixed a real bug neither branch's own
   version caught along the way: `MotionDetector._is_lifting` called
   `NumericPose.to_position()`, which does not exist (`NumericPose.position` is
   already a tuple) — fixed to read `poses[...].position[2]` directly, and the new
   `LiftDetector`/`StopLiftDetector` fixed the same way before being kept.
2. CI on that tip showed two failing `experiments` tests under `LongTermMemory`,
   flagged by the developer. Root cause: merging #295's `AgentInteractionEvent` in as
   a second base on `PickUpEvent`/`PlacingEvent`/`InsertionEvent` broke ORMatic's
   joined-table mapping, which maps a class to the SQL parent of the *first*
   already-mapped ancestor in its MRO — with `EventWithEffect` listed first, that
   parent was `EventWithEffect`, not `AgentInteractionEvent`. First fix (`0e580a146`)
   reordered the bases. Superseded by the developer's own cleaner fix (`12d806e20`):
   `AgentInteractionEvent` now extends `EventWithEffect` directly, so `PickUpEvent`/
   `InsertionEvent` need only single inheritance from it; `PlacingEvent` keeps
   `(AgentInteractionEvent, ComesToRestEvent)` for the physics-effect logic it shares
   with `SupportEvent`. Verified in isolation both times.
3. A fresh conflict against `origin/main` appeared after that push. Developer said yes
   to merging main in and resolving it now. `51fc40548` merges it — five files:
   `coraplex/plans/executables.py`, `coraplex/execution_environment.py` (not itself
   conflicted but carrying the same stale mechanism),
   `coraplex/robot_plans/actions/core/pick_up.py`,
   `test/coraplex_test/test_plan/test_executables.py`,
   `test/coraplex_test/test_designator/test_motion_designator.py`. The substantive
   call: adopted main's `Context.ticks_per_motion` design in full, removing
   `GiskardExecutable.max_ticks_per_motion_mapping`/`tick_limit`/
   `DEFAULT_MAX_TICKS_PER_MOTION_MAPPING` entirely (main's own rationale: the budget
   is a run policy, so it belongs on the context, not on class state that outlives
   the run) rather than keeping both mechanisms side by side. In `pick_up.py`, kept
   this branch's `if self.context.update_world_model_attachment:` guard around the
   trailing `ReAttachNode` (main's side of the conflict had dropped it) while adding
   main's `allow_gripper_collision=True` alongside this branch's existing
   `grasped_object=...` sizing parameter — confirmed both are independent,
   pre-existing `MoveGripperMotion` parameters, not alternatives, by reading the
   class definition first. Repointed one stray docstring reference in
   `experiments/tracy_experiments/trajectory_planning.py` to the new attribute name.
   Every touched file byte-compiled clean and re-checked for stray conflict markers
   before committing.

**Not yet known.** CI has not reported on `51fc40548` yet — nothing armed to watch it,
per the standing rule; ask, or look at the run.

**Unrelated, noted but out of scope.** A robokudo test failure seen earlier in CI
(`test_run_semdt_raytracer_ae_successfully`, object-hypothesis count 3 vs 2) — not
touched by anything in this round, left alone.

## #265: both outstanding items closed, #292 folded in, CI down to one field

**State.** `06e7af3eb` on `claude/icra-experiments-simulation-pipeline-w4ep7n`, a draft,
description up to date. #292 is closed as merged. Four commits this round:
`93cdd21c9` merges main, `7a6f8f7a9` migrates one stale `Match.variable` read,
`0e0bacfad` merges #292, `06e7af3eb` migrates one stale `failed_motions` keyword.

**CI.** Twenty-two of twenty-three checks passed on `0e0bacfad`; `krrood` came green,
confirming `7a6f8f7a9`. The single failure was `experiments`, on the renamed field that
`06e7af3eb` fixes. CI on `06e7af3eb` had not reported when this was written, and per the
standing rule nothing was armed to watch it -- ask, or look at the run.

**Next, if anything.** Nothing outstanding that this session can act on. The
`needs-resolution` label is still on the PR and looks like the stack tooling's, so it was
left alone.

**1. The merge conflict against main is resolved**, in the four files predicted, all
four keeping both sides:

- `world.py` - `memoize`'s new home `krrood.patterns.caching` beside this branch's
  `BeliefSource` import. This is the silent breakage the roadmap warned of: left as git
  merged it, the module imports a name its source no longer defines.
- `mapped_variable.py` - `CallVariable._update_type_` reads a method off its owner class
  when the child resolves to no type, and keeps this branch's `__call__`-class reading
  otherwise. main's own `test_method_call_chains.py` passes (8/8).
- `geometry.py` - main's `to_hex`/`from_hex`/`__hash__` beside this branch's `ColorName`;
  main's `RED`/`PINK` classmethods dropped, since this branch's answer with those colours.
- `test_color.py` - two files of one name, kept as one file of two sections (30 passed).

**2. The experiments job's blocker is in.** #292 merged whole, so the `RecordedLook`
rename, the 12 mm hole-placement fix and the requoted narrowing millimetres are all here.

**3. Two collisions main brought, neither predicted, both #192's shape.**
`MotionDidNotFinish.failed_motions` was renamed `unfinished_motions` by main's
`2664659b4`, whose own two readers pass the field positionally and so never changed; this
branch's `test_montessori_insertion_diagnosis.py` names it by keyword and exists on no
ancestor of that commit, so git flagged nothing. Migrated in `06e7af3eb`, assertion
untouched. And: `test_relational_circuit_registry_causal.py`
reads `query.variable`, retired by #192. Since #192 that builds an attribute expression
rather than raising, so what fails is `random_events` asking `issubclass` of `None`, in
another package. Standing hazard: every future merge of main can carry another, and none
will fail where it is written - re-run the convergence's `_is_own_name_` guard trick each
time.

**Correction to the last round.** `dae41889c` said left and right separate the cube from
the cylinder from no hole on this board. That was measured off hole bodies standing 12 mm
from the holes the look found; placed correctly, the square hole does lie between them.
All four direction choices still hold and none was reverted - #292 requoted the
millimetres and replaced the reason.

**Measured in the container** (`--orm-build=never`, with `pyjpt`/`matplotlib`/`flask`/`mypy`
installed): krrood 3014 passed / 2 failed (graphviz `dot`); sdt the same 45 failures as
pre-merge, its 45 added errors also on plain main (`iai_apartment`); experiments 684
passed / 18 failed, all ROS or database, identical pre-merge. CI on `93cdd21c9` was 13/15
green with exactly krrood and experiments red - the two these commits fix.

**Environment note, now stronger.** `pytest` is not blocked in a session container at all:
`--orm-build=never` skips the conftest's ORM generation. What still needs CI is the
generation itself and anything importing ROS (`coraplex`, `giskardpy`, `segmind` suites).

## 2026-09-09: the fast convergence - nine branches merged into #265

**Why.** The developer's own direction on #298's fourth review round (recorded on
`icra-foundation/roadmap.md` and tracking issue #252): merge everything in flight now
into #265, then #265 into `tracy_icra`, and cut new work off `tracy_icra` from then on.
This session (invoked as a `/plan-item-resolve icra-foundation
integrated-simulation-pipeline`) did the first half.

**What happened first.** The session's assigned branch
(`claude/icra-simulation-pipeline-merge-q4llqd`) turned out to be a fresh, empty branch
cut from `integration` - zero commits, invalid as a pull-request base - while this
item's real work was on `claude/icra-experiments-simulation-pipeline-w4ep7n` (#265),
638 commits deep. Confirmed with the developer before touching anything; the answer was
to work on w4ep7n directly, so everything below happened there instead of on the
assigned branch.

**Nine merges, in dependency order**, each at its own tip into w4ep7n, never sideways:
`simulated-camera-feeds-perception` (#298, clean), `scenario-domain-model` (#261, one
additive conflict in `generate_orm.py`), `run-results-recorded-into-sql` (#262, clean),
`episodes-recorded-through-ormatic` (#271, clean - retires
`montessori/results_recording.py` and `sorting_results.py` for the one `Episode` model),
`episodes-queried-by-eql` (#278, clean), `episode-artifacts-recorded` (#294, clean),
`montessori-scenarios` (#296, two additive conflicts), `question-set-and-ground-truth`
(#295, three conflicts), `paper-figures-from-episodes` (#297, one additive conflict).

**The one substantive conflict**, in `segmind/datastructures/events.py`: #295 adds
`AgentInteractionEvent` as a marker for "the agent acted on the tracked object";
`PickUpEvent`/`PlacingEvent`/`InsertionEvent` already carry
`EventWithEffect`/`ComesToRestEvent` for the physics effect each causes. Resolved by
multiple inheritance rather than choosing a side - `AgentInteractionEvent` declares no
fields, so the MRO composes cleanly. Verified in isolation (a standalone equivalent
class hierarchy) before applying it: `effect()` and
`isinstance(event, AgentInteractionEvent)` both hold for all three classes.

**Verification done.** Every merged/changed file byte-compiled clean; grep confirms no
stale reader of the two retired montessori modules. CI has not run yet on this tip - the
full workspace needs ROS and cannot be collected in this container - so this is
compile-clean and conflict-resolution-reasoned, not CI-green.

**A tooling bug found and worked around, not fixed.** `plan_item_bootstrap.py`'s
`record` subcommand assumes one `plan.yaml` indentation convention
(`ITEM_MARKER = "  - "`, `ITEM_FIELD_INDENT = "    "`), but this repo's plan.yaml files
actually use two different conventions and icra-foundation/icra-evidence use the other
one (`- id:` at column 0, fields at 2-space indent) - patching a field produces invalid
YAML. Its own test fixture (`bootstrap-plan.yaml`) encodes the same wrong assumption, so
the bug is untested rather than merely unhit. Not fixed here since it's shared tooling
outside this item's scope; worked around by hand-editing `plan.yaml`/`roadmap.md` in the
real format and pushing through `save-plan.sh` directly. Worth a `plan-tracking-skills`
item.

**A save-pr-progress.sh mistake, caught and fixed.** Ran the script with `--help`
(not a supported flag - it takes none) before ever editing this section for the new
work; it silently pushed the untouched placeholder scaffold (written for the originally
assigned, unrelated branch) onto w4ep7n's progress path, clobbering the real note above.
Recovered from the personal-notes branch's prior commit and restored in full before this
paragraph was appended.

**Status update.** `plan.yaml`: the eight merged items now `status: done` on
icra-foundation/icra-evidence (`simulated-camera-feeds-perception`,
`scenario-domain-model`, `run-results-recorded-into-sql`,
`episodes-recorded-through-ormatic`, `episodes-queried-by-eql`,
`episode-artifacts-recorded`, `montessori-scenarios`, `question-set-and-ground-truth`,
`paper-figures-from-episodes`); `integrated-simulation-pipeline` stays `in_progress`.
Roadmap sections appended for all nine. PR #265's description updated with the same
convergence table. Dashboards for icra-foundation/icra-evidence **not yet republished**
- `sync_manifest_status.py`'s drift check will (correctly) flag the eight `done` items
against their own still-open PRs, since "done" here means "content landed in the trunk",
not "this PR merged"; that's expected and explained in each item's roadmap entry, not a
real drift.

**Next.** `tracy-demo-takes-the-integrated-branch` - merging this branch into
`tracy_icra` and running the demo on the UR10 - needs the robot and is the developer's
to start. `icra-mechanism` has no in-flight branches yet (everything there is
`not_started`), so nothing from that plan needed merging this round.
