## shape-vocabulary-on-main (montessori-perception-split, layer 2) - #488, upstream cram2#804

Not a verbatim cut of #202 since 2026-11-12: unified with main's Tracy demo on #488 directly; the
shared vocabulary lives in SDT (semantic_annotations ShapeSortingPiece + kinds, shape_sorting_toy/).
Tests: `uv sync --extra dev --python 3.12`, then PYTHONPATH=<worktree>/*/src + domain_models/*/src,
CRAM_ORM_BUILD=never, <repo>/.venv/bin/python -m pytest. ROS-needing tests error locally.

Plan:
- Land once cram2#804 is re-reviewed and CI is green.

Done:
- 36aec5dad: merged main; one definition per duplicate in SDT; demo moved onto it; 676 SDT/experiments
  tests pass (59 ROS-only errors); SDT ORM regenerates. Demo test not run (needs ROS).

Next:
- CI on #488 36aec5dad (not polled), esp. test_each_lib (coraplex) for the demo test.
- Developer: update cram2#804's description, answer its 3 outdated threads.
- #202 and later layers adopt the SDT names when they merge main and #488 (posted on #486).
