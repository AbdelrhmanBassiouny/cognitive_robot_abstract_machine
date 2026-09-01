# episode-replayed-into-the-world (knowledge-directed-perception) - PR #246

Branch `claude/episode-replayed-world-kickoff-6ye5bb`, based on `sdt_segmind_krrood_from_fast_monitor` (#244),
the sdt/segmind/krrood/physics_simulators half of #169 split out at the developer's request (this session);
#169 stacks on #244 (native stack #173 dissolved, re-created as #247 with #244 at its foot).

## Plan (settled, see roadmap section)
- `RosbagPlayer(FilePlayer)` reading `/tf_static` + `/tf` + `/joint_states` with `rosbags`; sample-and-hold frames
  at `sampling_period`; poses only for `Connection6DoF` bodies, expressed in the root via the chain to
  `reference_frame`; joints positioned through `DataPlayer.get_joint_positions` (new hook), one batched update
  per frame; exceptions for nothing-to-replay and unrecorded reference frame.

## Done
- #244 opened, #169 re-based on it, stack re-created; eql-stack manifest/roadmap saved; issue #174 comment.
- #246 opened; manifest (branch/session/PR/in_progress) + kickoff roadmap section saved; issue #201 comment.
- Implementation committed and pushed (`195c271a`): player, exceptions, DataPlayer joint positions, rosbags dep,
  9 tests (`test/segmind_test`: 48 passed, 1 skipped; 39/1 before). PR #246 description updated.
- Roadmap "what it took" section saved.

## Next / outstanding
- #244 description: add local test results once the `main` baseline (worktree, PYTHONPATH) finishes and the failing
  sets are compared by name; fix its stripped `<paths>` placeholder line.
- Republish both dashboards (kdp and montessori-eql-stack) - the Artifact tool demands a full Read of each
  saved live copy first.
- Env recipe: `pip install -U uv` -> `/usr/local/bin/uv sync --extra dev --python 3.12`;
  `uv pip install --python .venv/bin/python rosbags docformatter`; pytest `--orm-build never`;
  ignore `test_robots/test_pose_facing.py`.
