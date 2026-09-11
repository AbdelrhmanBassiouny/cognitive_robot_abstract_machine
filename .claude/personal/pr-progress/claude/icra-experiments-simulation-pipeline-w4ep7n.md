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
