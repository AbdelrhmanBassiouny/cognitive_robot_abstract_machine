## EdgeFitDetector / ColorBlobDetector consolidation

Branch re-cut from `claude/icra-experiments-simulation-pipeline-w4ep7n` (it had been
cut from `integration`, which carries no detector code).

**Analysis complete, design presented, awaiting go-ahead. No source changed yet.**

Measured (opencv 4.11.0.86, pinned to match the convergence merge's own baseline):

- Six captures baseline: **6 missed / 2 invented, board found 6/6**. The merge
  (5382c1b2) recorded 6 missed / **1** invented; missed reproduces, invented does not.
  Deterministic across runs. On opencv 5.0.0.93 (what `uv sync` resolves) it is 5/2.
- `ColorBlobDetector` is **never chosen on any of the six captures** - `recorded_setup`
  states neither `finish` nor `color` for the lid, so both rule terms are False and
  every look falls to the edge fit. The captures are a guard on the edge-fit path, not
  evidence about the consolidation.
- Rendered matte lid (the only scene reaching both): identical category, agreement,
  outline array and pose; only `footprint` differs (fitted outline 0.00090000 =
  exactly 30mm sq., vs blob contour 0.00085400).
- Cost: whole `detect()` 67.4 ms edge fit vs 65.5 ms colour blob (3%). The fit alone is
  11.4 vs 5.7 ms but is only ~17% of the detector. The split's own 126/89 ms predates
  d8b65443, which narrowed the edge fit's sweep to a 24 mm believed reach.
- `EdgeFitDetector` reading a blob as `radius=0` + `YawInterval(theta, spread=0)`
  reproduces `ColorBlobDetector` **bit for bit** (cube at 0/17/30 deg, cylinder).
- Quarter-turn set collapses to one turn for cube and cylinder only; rect prism needs
  2, tri prism 4. Only cube and cylinder colour-separate from the lid today.

Real defect found: `ColorBlobDetector.detect` ignores `surface_pass.expected` entirely,
so on a matte surface a knowledge-directed expectation about a colour-separating piece
is silently dropped. `d8b65443` added that path to the edge fit only.

Next: on approval, implement the collapse (one detector; the blob becomes a tighter
belief), add the failing test for the dropped expectation first, re-run both harnesses.

Harnesses in scratchpad: `regression.py`, `rendered_lid2.py`, `cost.py`, `collapse.py`,
`radius_and_turns.py`, `turns_in_general.py`, `which_detector.py`. The pytest suite
cannot collect here (ORM generation needs ROS), as the merge commit also recorded.
