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

**Found, not fixed (design, for the developer).** A perturbation leaves no motion
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

