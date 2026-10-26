## shape-vocabulary-on-main (montessori-perception-split, layer 2) - #488, upstream cram2#804

Layer = files of #202 (montessori_perception_on_main), re-cut after every #202 change; geometry.py is
main's file plus #202's additions. Tests: PYTHONPATH=$(ls -d <worktree>/*/src | tr '\n' ':')
<repo>/.venv/bin/python -m pytest --noconftest (venv from `uv sync --extra dev --python 3.12`).

Plan:
- Land once cram2#804's reviewer is satisfied and its CI is green.

Done:
- cram2#804 review 2026-10-26: Hue.full_turn/decimal_places classproperties; Polygon2D
  alignment_angle_step/corner_match_tolerance fields kept by turned()/centered(); circle(corner_count=64)
  parameter. #202 880368fd3, #488 a0ed6304d; 84 passed.

Next:
- Developer: answer the 3 cram2#804 threads (no upstream comments from sessions); the circle thread
  was answered with a parameter, not a field.
- CI on #488 a0ed6304d and cram2#804 (not polled).
- #202 is conflicted with main (needs-resolution) and its description lacks the 2026-10-26 round.
