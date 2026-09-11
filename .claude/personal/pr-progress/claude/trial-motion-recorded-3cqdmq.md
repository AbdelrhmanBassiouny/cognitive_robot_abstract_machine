# claude/trial-motion-recorded-3cqdmq - PR #319 (draft)

Base: `claude/icra-experiments-simulation-pipeline-w4ep7n` (#265).
Session: https://claude.ai/code/session_013HepqhoucZF2H2cCjSizFP

## Done

1. giskardpy: `MotionStatechart.to_json`/`_from_json` carry `StateHistory`;
   `StateHistory`/`StateHistoryItem` are now `SubclassJSONSerializer`s. giskardpy test added.
2. experiments: `RecordedTrial.motions: List[RecordedMotion]` replaces the single optional
   `motion_statechart`. Observer gained `ran_the_motion` + `ObserverMotionListener`.
   coraplex `GiskardExecutable.execute` tells `Context.motion_listener`
   (`ReceivesExecutedMotions`). Listener threaded scenario -> `HaveTheRobotAct` step ->
   `SortingScene` -> `Context`. `WatchedSortingRun.trial_started` installs it.
3. record_episode: `PerturbationChoice.LIGHTING_CHANGED` dropped; argparse rejects it.
4. Draft PR #319 opened, description names the field shape and the reason.
5. Regression runs done for experiments, coraplex, giskardpy - every remaining failure
   is identical on the base branch (missing robot description packages on this runner).

## Established

A sorting trial runs **four** GiskardExecutables (pick up 2, put down 2 - coraplex splits
an action's plan at every execution boundary). Held-piece run: 2. Pushed run: 0.
Hence the list shape.

## Open, reported on the PR

A trial's chart does **not** survive the database (verified against real postgres: 4
motions and their spans come back, charts come back with 0 nodes / 0 history). Causes:
`MotionStatechartDAO` has no columns (every `MotionStatechart` field is `init=False`);
storing as JSON would need a world in `from_json` kwargs, which the engine's
`json_deserializer` does not pass; and nothing fills `Episode.world` yet. Separate change.

Tracy's URDF (`iai_tracy_description`) is not resolvable on this runner, so the headless
`record_episode.py --scenario robot-sorts-a-piece` cannot build its world here; the motion
counts and histories are proved on `SyntheticGrasperSortsAPiece` in the existing
simulation fixture instead.

## Environment notes (this container)

No ROS/venv on start. Set up with: newer `uv` (`pip install -U uv`), `uv sync --extra dev`,
ROS 2 Jazzy apt repo + `ros-jazzy-rclpy`, `-rclpy-message-converter`, `-std-srvs`, `-tf2-*`,
`-rosbag2-py`, `-nav2-msgs`, message packages, plus `xvfb` and `postgresql`.
Run tests as `source /opt/ros/jazzy/setup.bash && xvfb-run -a .venv/bin/python -m pytest ...`.
`docformatter`/`black` installed into `.venv` for `scripts/format_docstrings.py`.
