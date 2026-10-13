### Next
- Head-to-head soak against `stutter_montessori` at equal wall clock would put a number
  on the end-to-end gain; only this branch has been soaked so far.
- `RotationMatrix.rotational_error` reports some rotations the long way round; latent
  bug, ask the developer.
- Still untouched: `TFPublisher` evaluating compiled CasADi from the physics thread, and
  `MujocoSimulator.add_entity` swallowing a viewer Pause (mujoco_simulator.py:1731).
- `body.global_pose` remains unsafe off-thread; callers wanting numbers should use
  `numeric_global_pose` / `numeric_global_transform`.
- No PR opened yet.



### Next
- CI on `3e9f3847` is the real check; nothing about the merge was verified dynamically.
- The five branches stacked above this one, plus #176, #177 and #178, are stale by this
  merge and need restacking.
- `cramera/requirements.txt` is now the last of its kind (`main` deleted fourteen and
  moved to inline `pyproject` dependencies). Left alone so as not to conflict with #168.
- Earlier "Next" items below still stand: the head-to-head soak, `rotational_error`,
  `TFPublisher`, `MujocoSimulator.add_entity`, `body.global_pose`.
