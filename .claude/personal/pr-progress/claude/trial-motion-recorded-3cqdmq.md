# claude/trial-motion-recorded-3cqdmq - PR #319 (draft)

Base: `claude/icra-experiments-simulation-pipeline-w4ep7n` (#265).
Session: https://claude.ai/code/session_013HepqhoucZF2H2cCjSizFP

## Plan

1. giskardpy: `MotionStatechart.to_json`/`from_json` carry `StateHistory`. (done)
2. experiments: `RecordedTrial.motions: List[RecordedMotion]` replacing the single
   optional `motion_statechart`; observer gains `ran_the_motion`; coraplex
   `GiskardExecutable.execute` tells `Context.motion_listener`; watched run installs
   `ObserverMotionListener`. (done)
3. record_episode: drop `PerturbationChoice.LIGHTING_CHANGED`. (done)
4. Draft PR opened, description names the field shape and why. (done)
5. Full `test/experiments_test` and `test/giskardpy_test` runs for regressions. (in progress)

## Established

A sorting trial runs **four** GiskardExecutables (pick up 2, put down 2 - coraplex
splits an action's plan at every execution boundary). Held-piece run: 2. Pushed run: 0.
So the list shape, not the single field.

## Known gap, stated in the PR description

A trial's chart still does not survive the **database**: ORMatic maps `MotionStatechart`
to a table whose columns are all `init=False`, so it stores nothing; storing it as JSON
would need a world in `from_json`'s kwargs, and nothing fills `Episode.world` yet. That
is a separate change. The headless postgres run in the task's "Done when" was therefore
not carried out - it would record motions that come back empty.

## Environment notes (this container)

No ROS/venv on start. Set up with: newer `uv` (`pip install -U uv`), `uv sync --extra dev`,
ROS 2 Jazzy apt repo + `ros-jazzy-rclpy`, `-rclpy-message-converter`, `-std-srvs`,
`-tf2-*`, message packages, plus `xvfb`. Run tests as
`source /opt/ros/jazzy/setup.bash && xvfb-run -a .venv/bin/python -m pytest ...`.
