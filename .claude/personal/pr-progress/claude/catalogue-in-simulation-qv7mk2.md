Branch `claude/catalogue-in-simulation-qv7mk2`, draft PR
[#335](https://github.com/AbdelrhmanBassiouny/cognitive_robot_abstract_machine/pull/335)
targeting `claude/icra-experiments-simulation-pipeline-w4ep7n` (#265).

Done (6 commits, pushed)
1. `LayoutChoice.PARTIAL` wired to `PieceLayout.partial`.
2. Four cross-episode `LongTermMemoryQuestion`s: `EpisodesWhereInsertionFailed`,
   `HowOftenWasThePieceMoved`, `EpisodesWhereThePieceWasPickedUp`,
   `HasThisHappenedBefore`.
3. `experiments/src/experiments/montessori/run_corpus.py` + `experiments/scripts/run_corpus.py`.
4. Backend/predicate routing recorded on each scored query - without it
   `QueryLatencyByBackend` had no rows at all.
5. Fixed `ObjectsTheRobotMovedInTheEpisode` (and the other two "which objects"
   long-term questions) naming an object once per motion-x-pick-up pair rather than
   once - 85 of 300 askings wrong over the corpus.
- A 60-episode corpus was recorded and asked on the synthetic grasping robot; the
  accuracy-by-bucket table in the PR body comes from it, one row stale (the 0.970,
  which is the defect fixed in 5).

Left for a session at the lab (developer's own call, 2026-09-12)
- Re-run `run_corpus.py --repetitions 1` and `generate_paper_figures.py` on a checkout
  with ROS, Tracy, the camera and MuJoCo, and replace the table in the PR body.
  Re-running it here on the synthetic robot costs 4 hours and is not worth it.

Environment note
No ROS and no `iai_tracy_description` here, so `run_corpus.py` stops at `parse_tracy`.
Workspace installed in `.venv` (uv, python 3.12); tests run with `MUJOCO_GL=egl` and a
ROS stand-in on `PYTHONPATH` (scratchpad `rosstub/sitecustomize.py`, never committed).
