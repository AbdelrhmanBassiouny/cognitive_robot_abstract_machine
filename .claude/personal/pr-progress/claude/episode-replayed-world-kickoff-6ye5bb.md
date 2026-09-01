# episode-replayed-into-the-world (knowledge-directed-perception) - PR #246

Branch `claude/episode-replayed-world-kickoff-6ye5bb`, based on `sdt_segmind_krrood_from_fast_monitor` (#244),
the sdt/segmind/krrood/physics_simulators half of #169 split out at the developer's request (this session);
#169 stacks on #244 (native stack #173 dissolved, re-created as #247 with #244 at its foot).

## Done (2026-09-01, this session)
- #244 opened (3 commits, byte-identical to #169's tip on those paths); #169 re-based on it; stack #247 re-created.
  eql-stack manifest/roadmap saved (new item `sdt_segmind_krrood_from_fast_monitor`); issue #174 comment; dashboard republished.
- #246 opened; manifest (branch/session/PR/in_progress), kickoff and what-it-took roadmap sections saved; issue #201
  comment; dashboard republished.
- Implementation pushed as `195c271a`: `RosbagPlayer`, `segmind/exceptions.py`, `FrameData.joint_positions` +
  `DataPlayer.get_joint_positions`/`apply_frame`, `rosbags` dependency, 9 tests (`test/segmind_test`: 48 passed,
  1 skipped; 39/1 before). Descriptions of #246, #244 and #169 updated.
- Local baseline for #244 against `main` (worktree, PYTHONPATH): failing sets identical by name except
  `test_world_pr2.py` (env / copied generated ORM interface). Recorded in #244's description.

## Next (nothing owed by this session; for whoever picks it up)
- Wait for CI on #246 and #244. Replaying the real `tracy_pickup_demo` bag needs the bag on disk and the Tracy world.
- `expectations-from-events` reads the events a replay produces; it depends on this item.
- Env recipe: `pip install -U uv` -> `/usr/local/bin/uv sync --extra dev --python 3.12`;
  `uv pip install --python .venv/bin/python rosbags docformatter`; pytest `--orm-build never`;
  ignore `test_robots/test_pose_facing.py`; run the formatter with `.venv/bin` on PATH.
