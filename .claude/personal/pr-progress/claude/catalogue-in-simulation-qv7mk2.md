Branch `claude/catalogue-in-simulation-qv7mk2`, cut off
`origin/claude/icra-experiments-simulation-pipeline-w4ep7n` (#265). Draft PR targets
that branch.

Goal: the paper's accuracy, latency and determinism tables from a simulated corpus,
plus four cross-episode questions.

Plan
1. `LayoutChoice.PARTIAL` in `record_episode.py`, wired to `PieceLayout.partial`.
2. Four cross-episode `LongTermMemoryQuestion`s in
   `experiments/src/experiments/questions/long_term_memory.py`.
3. `experiments/src/experiments/montessori/run_corpus.py` + `experiments/scripts/run_corpus.py`:
   4 scenarios x 3 layouts x {no perturbation, each perturbation class} x --repetitions,
   headless, through `record_episode`'s own machinery; long-term catalogue asked five
   times per episode after the whole corpus is recorded; manifest of identifiers.
4. Nothing new in `paper/`.

Done so far
- nothing committed yet.

Next
- implement 1-3 test first, then generate the tables and open the draft PR.

Environment note
This container has no ROS install and no `iai_tracy_description`, so the Tracy scene a
simulated episode is built in cannot be built here. The workspace is installed in
`.venv` (uv, python 3.12) and the test suite runs with `MUJOCO_GL=egl` and a local
ROS stand-in on `PYTHONPATH` (scratchpad `rosstub/sitecustomize.py`, never committed).
