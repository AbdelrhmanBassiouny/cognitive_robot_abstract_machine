# episode-replayed-into-the-world (knowledge-directed-perception) - PR #246

Branch `claude/episode-replayed-world-kickoff-6ye5bb`, based on `sdt_segmind_krrood_from_fast_monitor` (#244),
which is the sdt/segmind/krrood/physics_simulators half of #169 split out at the developer's request
(this session); #169 now stacks on #244 (stack #173 dissolved and re-created with #244 at its foot).

## Plan
- `RosbagPlayer(FilePlayer)` in `segmind/players/rosbag_player.py`, read with `rosbags` (pure Python, declared
  in `segmind/pyproject.toml`): sample `/tf_static` + `/tf` + `/joint_states` at a fixed period into `FrameData`
  (latest transform per frame, latest position per joint). Poses only for bodies whose parent connection is a
  `Connection6DoF`, expressed in the world root via the chain up to the reference frame (`map`); robot link
  frames ignored. Exceptions: bag without any of the three topics; reference frame never published.
- `FrameData.joint_positions`; `DataPlayer.get_joint_positions` hook (default empty); poses + joints applied per
  frame under one `world.batch_state_changes()`. Remove `JSONPlayer.get_joint_states` stub.
- Tests first (`test/segmind_test/test_episode_replay/test_rosbag_player.py`, bag written into tmp_path by a
  helper in the segmind test dataset): sampler (count/times/latest wins); frame-to-world mapping on a hand-built
  world (chain, ignored link, unknown frame); end-to-end replay (world moved; LossOfSupport/Support events over
  `_simple_apartment_setup` with an unchanged `EpisodeSegmenterExecutor`).
- Env: `/usr/local/bin/uv` 0.12.8 (`pip install -U uv`), `uv sync --extra dev --python 3.12`, then
  `uv pip install --python .venv/bin/python rosbags docformatter`; run pytest with `--orm-build never`
  (giskardpy ORM generator fails here as on main); ignore `test_robots/test_pose_facing.py` (collection error, env).

## Done
- #244 opened (3 commits, byte-identical to #169's tip on those paths); #169 re-based on it; stack re-created.
- #246 opened as draft; manifest updated (branch/session/PR/status), roadmap section appended, saved.
- Extraction test run over segmind + krrood ormatic/verbalization + sdt spatial/geometry/predicates/robots: running.

## Next
- eql-stack manifest: add item for #244, make 169 depend on it, roadmap note, save, dashboard, issue #174 comment.
- Implement tests then player; format_docstrings; push; update #246 and #244 descriptions; dashboards.
