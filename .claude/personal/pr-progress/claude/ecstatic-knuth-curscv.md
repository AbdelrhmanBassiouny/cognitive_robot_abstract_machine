## shape-vocabulary-on-main (montessori-perception-split, layer 2) - draft #488

Cut from #202 tip 4653fe32e; branch off main 236b295a2.

Done:
- Bootstrap commit, draft PR #488, manifest open+record (in_progress), roadmap section, dashboard republished.
- 1fc3188fb: 7 files verbatim from 4653fe32e (semantics, exceptions, hole_geometry, board.stl, pieces,
  test_montessori_semantics, test_montessori_hole_geometry) + new test_montessori_pieces.py (3 pieces-only
  colour tests moved verbatim; the 2 SurfaceColors tests + _painted stay for detection-pipeline-on-main).
  Co-authored-by sorinar329.
- 25 passed with --noconftest in `python3 -m uv sync --extra dev --python 3.12` venv (system uv 0.8 too old
  for pyproject; pip-installed uv 0.12). With conftest: ORM generation CouldNotResolveType MetaData - same on
  plain main locally.
- PR description written.

Next: CI result on 1fc3188fb (not polled). Then developer review. Re-sync if #202 moves.
Flag (in roadmap): test move makes final merge into #202 not file-neutral for test files.
