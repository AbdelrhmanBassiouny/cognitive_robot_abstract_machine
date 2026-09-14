## robot-sorting-records-the-run: the real sorting demo records what the recorder records (2026-09-13)

**Session.** https://claude.ai/code/session_01DW221gKgpaa45K7i2yx9kf

**Branch.** `claude/robot-sorting-records-the-run-9f2ktq`, stacked on #265; draft PR
against #265 with the `bug` label. Schema (`episodes/episode.py`) untouched. #356 is not
merged into #265 and shares the same schema byte for byte; its only overlap with this
branch is `paper/camera_frame.py` (it adds panels beside `BagFrameAt`, this branch
changes how `BagFrameAt` finds its frame).

**Plan / done.**
1. Motions: `_SortingRig.__post_init__` puts `ObserverMotionListener` on its context. Done.
2. Person: `SceneThePersonSetUp` (watched_run.py) extracted from `WatchedSortingRun`
   (`pieces_placed`, `stated_over`); `SortingScene.as_set_up`/`piece_as_named` own the
   assembly; the demo's `SortingTrial.state_the_scene` uses it and
   `question_set_about` takes the scene. Done.
3. Perturbation: `--perturbation piece-shoved|target-hole-moved --piece`;
   `PerturbationChoice.aimed_at` (record_episode) builds it; `SortingTrial.bring_about_the_perturbation`
   tells the person, `observer.carried_out`, forgets where the moved thing stood, looks
   again; `Episode.perturbation_names` named. Done.
4. Joinable: bag kept as `files/bag` (`EpisodeArtifacts.keep_camera_recording`, `RunFile`
   moved to artifacts.py) by the demo and record_episode; `TrialClock.instant_of`/
   `stamp_of`/`seconds_of_stamp`; `RecordedCamera.colour_stamps`/`image_nearest`;
   `BagFrameAt`/`BagFramesAround` read by the trial clock instead of a fraction. Done.
5. Tests: demo 29, artifacts, paper camera frames, run plan, record_episode,
   recorded camera (new, writes an mcap), rosbag process (end-to-end stamps within the
   trial). Regression run over touched modules in progress at the time of writing.

**State.** Committed (`584ac5edfc`, `c0cba283ad`), draft PR #361; at the developer's request
fast-forwarded into #265's branch (`c0cba283ad`) and pushed, so #361 is merged and the
checkout is on #265's branch. Not run on the robot. Possible follow-ups for the developer: `EpisodeArtifacts.keep_directory`
now has no caller outside tests; `pickup_demo_real` could join `pickup_demo_mujoco` in
generate_orm's ignore list (it maps `_SortingRig`/`SortingTrial` as junk tables).
Later the same day: #363 (numbered pieces menu) merged into #265 too (`bb8c41c4b4`).

## string-enum-survives-json: a StrEnum member came back from the robot's world as a string (2026-09-13, night)

**Session.** https://claude.ai/code/session_01DW221gKgpaa45K7i2yx9kf

**Branch.** `claude/string-enum-survives-json-9f2ktq` off `main`, draft PR #365 (`bug`),
one commit `f79f90ceb7`; cherry-picked onto #265 as `0a955eb721`, with the world-level
test `409e42612c` on #265 only (its files exist on no ancestor of `main`). Pushed both.

**Cause.** `record_episode --execution real ... --perturbation piece-shoved` died at the
first trial's commit: `ShapeSortingHoleDAO.shape_category` was the bare string
`'cylinder'`. The board came from the world the robot publishes, stood by an earlier run
and rebuilt from the world service's JSON; `krrood.adapters.json_serializer.to_json`
returned any `str` as a leaf, a `StrEnum` member included, so the member was lost.
Confirmed offline: `to_json(hole)['shape_category'] == 'cylinder'`.

**Fix.** `to_json` writes an `enum.Enum` member through `EnumJSONSerializer` before the
leaf check. Tests: two in `test_json_serializer.py` (JSON names class and member; round
trip through JSON text gives the member `is`), one in
`test_montessori_scene_publishing.py` (board published, world rebuilt as the service
serves it, holes' categories are the members). All three failed before the fix.

**Verified.** krrood 2382 passed (1 pre-existing failure in `test_rspns.py`, also without
the change); sdt adapters+ros 303 passed (3 marker-timeout failures in the full-directory
run pass alone, with and without the change); experiments JSON/recording/demo modules
237 passed; giskardpy statechart JSON + coraplex perception + segmind 367 passed.

**For the developer.** Restart the bringup (world service) before the next recording: a
server started before the fix holds the earlier board's categories as strings in memory
and serves them as strings regardless. `PolymorphicEnumType.process_bind_param` could
raise a named exception when handed a non-member instead of the bare `AttributeError`
that sent the trace into SQL -- left out to keep #365 to one root cause.
## episode-audit: the three real stand-still runs checked, and what the check found (2026-09-14, small hours)

**Session.** https://claude.ai/code/session_01DW221gKgpaa45K7i2yx9kf

**Asked.** Health, logic and score check of the three real `scene-stands-still` runs
of 2026-09-13 22:00-22:54 (`2f37062677`, `d37b712da5` piece-shoved, `6ffe9ec2ef`
target-hole-moved; 3 trials each, bags kept), a command to check any recording, and
the commands for the real sorting recordings.

**Built, on #265.** `experiments/scripts/check_episode.py` (module
`experiments/episodes/audit.py`, main in `experiments/montessori/check_episode.py`):
`--episode ID...`, `--latest N`, `--real`, `--database-uri`; one finding per check
(rows, world meshes present, transcript, joint traces, camera recording spanning every
trial with a frame decoded at each question moment / video, questions, events,
perturbation carried out and noticed, outcomes alike, scores by bucket naming every
wrong answer, read back whole through LongTermMemory); exit 1 on any FAILED. Tests
`test_episode_audit.py` (25) and `test_episode_audit_camera.py` (4, rosbag).

**Fixed, on #265** (each its own commit, each with a failing-then-passing test):
1. `7fcc2753e6` a recorded world's meshes are kept beside the artifacts before the world
   goes into the database (`keep_meshes_of` in artifacts.py, called by
   `RecordsTrialsToADatabase.record`; `MeshFileStorage.is_in_a_root`). Cause: a world
   fetched from the robot rebuilds every mesh into the /tmp root removed at exit, so all
   three real episodes' worlds name 65-79 files that are gone -- `recall_trials` and the
   paper-figures job die in trimesh on them. The three episodes' geometry is
   unrecoverable; re-record them (the check now passes on a fresh recording).
2. `240243a5de` (cherry-pick of #367, off main, `bug`): `Mesh._from_json` dropped the
   colour, so run 3's pieces (reused from the fetched world) answered all-white.
3. `26e73cea5f` joints ground truth counted a shared DoF once per connection (Tracy 24
   vs 14) -- `NumberOfOwnDegreesOfFreedom` scored wrong in every trial of the corpus.
4. `b8c2bd3a93` colours truth compared position by position; same answer scored t/f/t.
5. `13e2104bcc` transcript "Ran: 1" -> the member's name.

**Fixed later the same night, at the developer's direction** ("the translation
detector should handle big sudden moves as a translation event if the distance is not
already claimed by another translation event"): `c77d938735` segmind
`TranslationDetector` compares with `SegmindContext.rest_poses` (first sight, then
where the last translation stopped), reports an unclaimed change of place beyond
`distance_threshold`; `a8c66997f3` the monitor ticks once on `start()`; `bf62af5ed2`
`trial_started(scenario, world, perturbations)` and `watched_category` prefers the
perturbation's piece. End-to-end tests in MuJoCo and over the tape capture answer
`AnythingMoved` True after a shove. All pushed to #265 (`bf62af5ed2`).

**Found, not fixed (design, for the developer), as first written.** A perturbation leaves no motion
event, on the robot or in simulation (`AnythingMoved` False after "Push the cube 10 cm"
in every perturbed stands-still trial, sim and real): the person acts between two
looks and the second look re-stands the body, the monitor ticks once per step. The
run knows the perturbation and where the piece was before and after the look, so it
could hand the observer a `TranslationEvent` of what the two looks saw. Also: the
monitor watches the first piece, not the one the perturbation acts on
(`watched_category`); `TheSceneIsUndisturbed` ignores the board, so target-hole-moved
trials read SUCCEEDED; a joint trace samples only on state change, so a still robot
leaves an empty one (2f37: 0 samples). record_episode's sorting scenarios refuse
`--execution real` (`runs_on_the_robot` False) -- the real sorting recordings go
through `pickup_demo_real` (one trial per run).

**The other session** (in ~/bass) reported the same two health findings (meshes, joint
traces) and offered a row repair of the robot links by body name; not done here.

## pickup-demo-rehearsal: the real sorting demo rehearsed and checked without the robot (2026-09-14, morning)

**Session.** https://claude.ai/code/session_01DW221gKgpaa45K7i2yx9kf

**Asked.** "Mimic as close as possible the recording and the health check of real
robot sorting trials without the real robot and the real camera", so the lab holds
fewer surprises.

**Built, on #265.** `experiments/tracy_experiments/lab_without_the_robot.py`: the
lab's ROS side served by this process -- `PublishedWorld` (Tracy's description over
`FetchWorldServer` + `WorldSynchronizer`), `CaptureCamera` (a capture's colour, depth
over both transports, calibration, static TF of its pose; `show()` swaps the capture),
`GripperDriverInTheWorld` (the `ParallelGripperCommand` action per arm, closes the
knuckle in the served world, stalls on a piece within 6 cm of the tool frame, publishes
`/<side>_gripper/joint_states`), `JointStatePublisher`, `LabWithoutTheRobot.brought_up`.
`pickup_demo_rehearsal.py`: `Rehearsal.run()` brings the lab up, connects through
`LiveTracy.connected` verbatim, runs `PickupDemo` with Giskard SIMULATED in-process and
a scripted `PersonAtTheRehearsal`, records to `<artifacts>/rehearsals.db`, audits, prints
the `check_episode.py` command. Script `experiments/scripts/rehearse_pickup_demo.py`.
`pickup_demo_real.main` refactored into `PickupDemo` (fields: tracy, person, database,
asked_about, perturbation, bag, motion_execution, artifact_directory, feed);
`argument_parser(add_help)`; `bag_asked_for`; `CHECK_THE_SCENE` goes through
`person.carry_out`.

**Found by rehearsing (fixed).** (1) segmind `EventCallbacks` registered a callback
twice for kinds reached by two inheritance paths (every event noted twice) -- #371 off
main (`bug`), also on #265. (2) The bag opened *after* the trial's clock started, so
every real recording would have warned "recording begins N s into the trial" --
`trial.begin()` now inside the recorder block. (3) `LiveTracy` spun a
`MultiThreadedExecutor`: a motion whose ticks the synchronizer publishes took 47 s
beside it and 0.8 s beside a `SingleThreadedExecutor` (rclpy's multi-threaded executor
spins hot while a callback runs); every callback of the node is in one mutually
exclusive group anyway, so switched -- this hits the lab too. (4) `LiveTracy` destroyed
its node while a look was still running on the executor (`InvalidHandle` at exit) --
spinner joined first. (5) Raw depth best-effort over loopback is mostly lost; the
stand-in publishes it reliably.

**Found later the same morning (fixed).** (6) `Plan.initial_world` copies (17 per
sorting trial) carried temp-root mesh paths → a trial read back only in the writing
process; `RecordsTrialsToADatabase.record` keeps the meshes of every world a trial
records, the audit checks the plans' worlds too (`8fbddff9d3`). (7) The synchronizer's
depth-10 subscription dropped state updates while the demo's executor was inside a
look; the gripper's close never reached the demo world (trace knuckle 0 throughout).
`UPDATE_QUEUE_DEPTH = 1000` in sdt's `world_synchronizer.py` (`fac4de65b7`, #372 off
main, `bug`). (8) `trial.finish` ran after the bag closed → "recording ends N s before the
trial" (`5fce6d2f4c`). Note: a recalled plan's `initial_world` comes back as a
`WorldMapping`, not a `World` (coraplex `PlanMapping.to_domain_object`) -- reported,
not fixed.

**Rehearsal timings.** Whole rehearsal with bag ~85 s (perceive 2 s, park+4 sorts ~35 s,
record ~20 s, audit). Report: all PASSED except camera recording (fixed by 5) -- see run.

**Tests.** `test_tracy_lab_without_the_robot.py` (7), `test_tracy_pickup_demo_rehearsal.py`
(12; two module-scoped rehearsals, ~3 min), `test_segmind_detectors`'s sibling
`test_event_callbacks.py` (3).

**Left.** A perturbation can only be rehearsed with a second capture
(`--capture-after`); none of the shipped captures shows a shoved table, so the rehearsal
reports the perturbation WARNING (nothing moved). Take a before/after capture pair at
the lab with `capture_from_camera` to rehearse it later.

## robot-reach-and-rehearsal-exit: the nine-item list of 2026-09-14 (midday)

**Session.** https://claude.ai/code/session_01FDXKmgDQuFEQPonF7H2ni7

**Robot error first.** `pickup_demo_real.py` on the robot died on its first reach with
`GiskardWorldUpdateNotReceivedError` (update not within 30 s). Cause: this morning's
single-threaded `LiveTracy` executor runs the camera's look (inside the colour callback,
pipeline-long) on the same thread as the world synchronizer; rclpy takes one message per
subscription per round, so a motion's ticks drained one per look. Fix `4c0e77ead0`
(pushed): camera on its own node + `SingleThreadedExecutor` (`SpunNode`). Test in
`test_tracy_lab_without_the_robot.py` (200 ticks at 100 Hz within 10 s). Tests and
rehearsals must use their own `ROS_DOMAIN_ID` + `ROS_AUTOMATIC_DISCOVERY_RANGE=LOCALHOST`
while the bringup is up (domain 2): the lab stand-in otherwise talks to the robot's graph.
`--record` only adds the bag; the episode always goes to the database -- asked the developer.

**Plan / done (items 1-3 of the list).**
1. Recalled plan world is a `WorldMapping`: krrood orders alternative-mapping conversion
   by declared pre-build classes only; `PlanMapping` declares none. Fix in
   `from_dao.py` (`_conversion_order`: held mapping before holder unless it reverses a
   declared edge). PR #374 off `bass/main` (`bug`, first branched off `origin/main` =
   ACRAMbly by mistake, rebased and force-pushed at the developer's request), cherry-picked
   onto #265 (`3f2f32f5f7`, to be amended with the experiments test). Asked the developer
   whether `Plan.initial_world` should be recorded at all (17 worlds per sorting trial).
2. `ask_episode.py --at`: `ask_at_a_moment`, `MomentOutsideTheTrial`, `AnswersAtAMoment`,
   `JointPositions.standing_in`; first trial only. Tests 20 + 23 passed.
3. Exit race: `MontessoriPerceptionNode.stop_looking` (+ `LookingHasStopped`), called by
   `PickupDemo.run` before `keep_the_episode`. "rcl_shutdown already called" = rclpy's
   SIGINT handler shutting the context before `main` (traced: nothing else does); rehearsal
   `main` uses `try_shutdown`, test in `test_tracy_pickup_demo_rehearsal_interrupted.py`.
   Traced rehearsal after the fixes: clean exit, audit PASSED except the camera-recording
   WARNING (CLI keeps 1 frame in 10; first kept frame 2.6 s in; not a robot problem).

**Developer's answers (2026-09-14).** Recording the episode stays the default, with a
`--no-episode` flag to run without one (new work, test first, after 1-3 are pushed).
`Plan.initial_world` keeps being recorded. The three unreadable real stand-still episodes
of 2026-09-13 are to be re-recorded on the robot, not repaired.

**State.** Items 1-3 committed (`5b790a4076`, `811b077e1e`, `f1f8e30927`) on top of
`4c0e77ead0`; final-tree reruns: lab 8, rehearsal 12, recording 25, pickup_demo_real test
module + audit 55 passed. Pushed to #265 (`f1f8e30927`), still a draft, description section
"Fixed 2026-09-14 (midday)" added. `--no-episode` done: `a90a043885` (pushed; 
`database_asked_for`, `PickupDemo.keep`; demo test module 32 passed). Open question to the
developer: the rehearsal inherits `--no-episode` and ignores it -- refuse it there?

**Item 4 in progress.** #356 merged locally as `3ed1eb4c58` (not pushed). Five conflicts:
trace.py (both added a joints reading -- kept #356's `JointPositions.of` + `standing_at`,
ask_episode uses `standing_at`), camera_frame.py + its test (this branch's `RunFile` in
artifacts.py and trial clock, #356's `TwinFrames`), query_card.py (#356's `bagged` with the
trial clock), pickup_demo_mujoco.py (camera moved to `tracy_experiments/camera.py` by #356;
camera.py now holds this branch's `camera_link_T_optical(world)` from 7aa4013ae8, demo
re-exports the names its tests read). #356's trace fix kept. Hazard: `camera_link_T_optical`
looks up `tracy_mount`, which a world fetched from the real robot may not hold -- check
when rendering real episodes' cards. #356 needs `pyrender`; the venv lacked it, installed
`pyrender` and `freetype-py` with `--no-deps` (PyOpenGL kept at 3.1.10). Cards of
`1b5069d9e4ae4954af65dbbc77b71e21` draw (4 cards: objects seen, picked up recently, own
DoF, event against the plan; side-of-another-object not asked by that run). Silent merge
break fixed `269a35a911`: `FramesByMoment.write` is abstract here (7f5e9376dd), #356's
`TwinFrames` had none -> TypeError on every twin camera panel; `TwinFrames.write` + 2 tests
(frames-around module 19 passed). Scene panels of the rehearsed episode hide the pieces
behind the arm -- to report, not fixed. Merge suite 144 passed (4 failed = the TwinFrames
break, before the fix); fixed-tree rerun 84 passed. Pushed (`269a35a911`), #265 still draft,
section "Merged 2026-09-14 (afternoon)" added. The only REAL episodes with a world in the
lasting database are the three unreadable ones, so the `tracy_mount` camera hazard waits
for the re-recording.

**Item 5 in progress (developer chose "record it, then check").** Found: the record never
said which piece a perturbation acted on or when, and in the pickup demo no monitor ran
while the person acted (monitors start inside each sort; the shove comes after the park
plan). Built (uncommitted): `MovedBySomeoneElse(moment, things_moved)` on `RecordedTrial`
(schema change, ORM regenerated, never tracked); `EpisodeObserver.carried_out(instruction,
moment, things_moved)`; watched run records it before bringing the perturbation about;
pickup demo records it before the person acts and `_SortingRig.watching(things)` ticks a
`build_translation_monitor` before the person acts and after the look; audit
`TrialRecord.noticed_what_someone_else_moved` = a TranslationEvent of what was moved
between the instruction and the next plan start (falls back to AnythingMoved where no
move was recorded, so old episodes and existing tests read as before). Tests: 2 observer,
2 audit, 1 watched run, 1 demo; all 6 pass, watched run 29 passed. Rehearsal module
exposed two things: (a) `test_the_person_is_asked_to_bring_the_perturbation_about` pinned
the old PASSED reading -- developer approved changing it to expect WARNING (the capture
never shows the shove; item 9's `--shove-shown` is where it PASSES); (b) the interrupted
rehearsal test is racy: rclpy's own SIGINT handler shuts the context from its signal
thread (no on_shutdown callbacks run), `try_shutdown`'s `ok()` check races it. Fix: the
rehearsal `main` inits with `SignalHandlerOptions.NO` and `rclpy.shutdown()`s itself;
new test `test_an_interrupted_rehearsal_is_shut_down_by_the_command_itself` (on_shutdown
thread is MainThread) fails 3/3 on the old code, both interrupted tests pass 3/3 after.
Separate commit from item 5.

**Item 6 (uncommitted, tests green).** Developer: delete `pickup/main.py` (half-written
stacking copy, nothing imports it) -- `git rm`'d. Stacking + Montessori real demos spin
via `live_tracy.SpunNode` (single-threaded, joined before destroy); `NODE_NAME` constants
document why. Test `test_tracy_real_demos_spin_one_thread.py` (stands in for the Giskard
launch; the world fetch reads `node.executor`) failed on both demos before, passes after;
`test_tracy_montessori_actions.py` still passes.

**Item 8 decision.** Developer: runs sample the joints as the trial begins (pickup demo
`SortingTrial.begin`, watched run `trial_started`); `JointTraceRecorder`'s contract and its
four tests stay.

**Pushed to #265 (`e91793a345`, still draft, description sections "Fixed ... (afternoon)"
and "(late afternoon)" added):** item 5 `b2e78aea2b`, rehearsal shutdown
`e01c1d749e`, item 6 `77f84e2a6a`, item 7 `4279f2bd6d` (`TheSceneIsUndisturbed.board_stood_at`,
scenario `starting_board_place`; MuJoCo TargetHoleMoved + tape-capture slid board tests),
item 8 `e91793a345` (sample moved to the very start of `trial_started`, else the first
sample was 0.12 s in). New tests all failed first, pass after. Pre-push: 127 + 50 + 87 + 22
passed.

**Item 9 pushed to #265 (`cee219f6e7` + `9b3c7f5dc9`, still draft, description section
"Rehearsed 2026-09-14 (evening)" added).** Pre-push: rehearsal module 17 passed twice in a
row; lab/camera/publishing/demo/recording/audit 134 passed. End-to-end shove rehearsal PASSED
the perturbation check alone but WARNED inside the full rehearsal module. Cause (its own
commit `9b3c7f5dc9`): `hold_board` -> `read_with` after the person
acts, but the node's next look took the next colour image off the subscription queue
(sensor-data QoS depth 5, stand-in sends every 0.25 s, a look ~2 s), i.e. one sent before
the shove was shown. Fix in `MontessoriPerceptionNode`: no look of a colour image sent
before the handover, stamps read against the node clock by the shortest stamp-to-arrival
delay seen (real camera stamps with this machine's clock, ~0.6 s latency, measured off the
2026-09-13 22:01 bag; `camera_replay.py` replays day-old stamps, which a plain clock
comparison refused forever); stops asking once one image sent after it arrives (looped
bag). 3 tests in `test_montessori_live_camera.py`, each seen failing (stale 3/3; replay vs
clock comparison; loop with the reset removed); module 24 passed. All ten items of the list are now done except item 10, the
re-recording, which is the developer's to run.
`lab_without_the_robot.CaptureOfAShove` (detects the
piece, inpaints where it stood, warps its pixels through the plane of its top by the
shove, writes a new capture `<name>_shoved`); `Rehearsal.shove_shown` +
`--shove-shown METRES` (direction = the perturbation's displacement), refused without
`PieceShoved` (`ShoveShownWithoutAShove`); the person shows the shoved capture, made in a
temp dir inside `run`. Fast tests pass 3/3 (shoved cube found moved within the tape
tolerance, others unmoved); the end-to-end rehearsal expecting PERTURBATION PASSED is
running. The re-recording of the three unreadable episodes is the developer's to run.

## episode-check-noise-and-board: the re-recorded real stand-still runs checked (2026-09-14, night)

**Asked.** Check and fix what `check_episode.py` warned on for the three new real
stand-still episodes (`508e367a…` unperturbed, `0a793ded…` piece-shoved, `c2efb7db…`
target-hole-moved; 3 trials each, all health checks PASSED).

**Done, pushed to #265 (`98bec17de0`, still draft, description section "Checked
2026-09-14 (night)" added).** `60bd6c165e`: `PlaceOfOwnBody` true answer is
`PlaceStoodAt` (position within `HOW_FAR_A_PLACE_MAY_DIFFER`; `PlacesPutAt.near`
delegates) -- joint noise 1-1.6e-4 rad between ask and ground truth scored it wrong at
random. `98bec17de0`: `WatchedSortingRun.apply_perturbation` wraps the perturbation in
`watching_translations_of(not_watched(things_moved))`
(`build_translation_monitor_in_scene`, `translation_detectors_of` shared with the Tracy
monitor module) so a slid board is seen translating. FAILED outcomes of the perturbed
episodes are correct by design. Tests: questions 35, watched run 30, pickup demo real +
audit + ground truth + record_episode 163 passed.

**Left.** Recorded rows of those three episodes keep old scores / no board event
(`ask_episode --rescore-working-memory` does not rescore `PlaceOfOwnBody`); a new
target-hole-moved recording is what shows the board fix. `WatchedSortingRun.watching_translations_of`
and `_SortingRig.watching` in pickup_demo_real are near-duplicates -- candidate to unify.
Orientation of a link is no longer scored -- asked the developer implicitly in the chat.

