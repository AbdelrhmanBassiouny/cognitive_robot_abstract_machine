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
