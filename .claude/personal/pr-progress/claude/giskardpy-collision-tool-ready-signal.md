## PR #490 - giskardpy collision matrix tool: SIGINT only once ready (bug)

Why: the second flake behind #229's red CI run 37040000560 (sibling of #489).
test_script_launch_and_kill slept 5 s, then sent SIGINT. Probed in the CI image:
SIGINT at 0.3 s gives ImportError (rclpy C ext) and exit 1; at ~2.5 s the signal
is lost and the tool hangs. The tool is ready about 7 s after launch.

Done:
- Test first: the test waits for tool.READY_MESSAGE (stdout and stderr merged,
  STARTUP_TIMEOUT_SECONDS=120). It failed before the fix ("not ready in time").
- Fix: the script prints READY_MESSAGE via QTimer.singleShot(0, announce_ready)
  before app.exec_(). Passes 5 out of 5, and 3 out of 3 under full CPU load;
  the whole test file passes (6).
- Draft PR #490 off main, labelled bug.

Open:
- SIGINT during the tool's own start-up still exits 1 or is lost. That's a
  separate script defect, not fixed here.
