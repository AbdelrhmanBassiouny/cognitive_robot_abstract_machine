Branch `claude/catalogue-in-simulation-qv7mk2`, cut off
`origin/claude/icra-experiments-simulation-pipeline-w4ep7n` (#265). Draft PR targets
that branch.

Goal: the paper's accuracy, latency and determinism tables from a simulated corpus,
plus four cross-episode questions.

Done
1. `LayoutChoice.PARTIAL` wired to `PieceLayout.partial` (commit e0851f64e6).
2. Four cross-episode `LongTermMemoryQuestion`s: `EpisodesWhereInsertionFailed`,
   `HowOftenWasThePieceMoved`, `EpisodesWhereThePieceWasPickedUp`,
   `HasThisHappenedBefore` (e0851f64e6).
3. `experiments/src/experiments/montessori/run_corpus.py` + `experiments/scripts/run_corpus.py`
   (51cd115ead), plus recording which backend answered each predicate, without which
   `QueryLatencyByBackend` had no rows at all - nothing in the pipeline wrote
   `RecordedQuery.answered_predicates`.
- Branch pushed.

Next
- finish the demonstration corpus (60 episodes recorded, asking phase running), run
  `generate_paper_figures.py` over it, paste the accuracy-by-bucket table into the PR
  and open the draft PR against #265's branch.

Environment note
This container has no ROS install and no `iai_tracy_description`, so the Tracy scene a
simulated episode is built in cannot be built here: `run_corpus.py --repetitions 1`
gets as far as `parse_tracy` and stops there. The demonstration corpus is the same
60-episode plan run on the test suite's synthetic grasping robot instead.
The workspace is installed in `.venv` (uv, python 3.12); tests run with `MUJOCO_GL=egl`
and a local ROS stand-in on `PYTHONPATH` (scratchpad `rosstub/sitecustomize.py`, never
committed).
