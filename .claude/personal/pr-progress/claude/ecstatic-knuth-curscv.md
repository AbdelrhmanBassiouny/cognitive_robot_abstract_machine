## shape-vocabulary-on-main (montessori-perception-split, layer 2) - #488, upstream cram2#804

No longer a verbatim cut of #202 (developer, 2026-11-12): unified with main's merged Tracy demo on
#488 directly. Tests: <repo>/.venv/bin/python -m pytest (venv from `uv sync --extra dev --python 3.12`).

Plan (2026-11-12, developer's choices: #804's definitions win, shared home is SDT, SDT gets the set):
- Merge main into the branch, resolving geometry.py / shape_collection.py.
- SDT: ShapeSortingPiece (+ Cube/Cylinder/... subclasses), ShapeSortingHole, ShapeSortingBoard
  annotations; board mesh + hole reading (one board.stl); PieceHue + piece sets (grasp_height passed in).
- Remove main's duplicates: Mesh.triangular_prism, demo's HoleShape/HoleOutline/BoardHole/
  HoleShapeClassifier/BoardGeometry/ShapeSortingPieceSet, demo's board.stl; demo body builder renamed.
- experiments keeps only perception matching of a set (hue tolerance).
- Tests moved with the code; run sdt, experiments, coraplex demo tests.

Done:
- cram2#804 review 2026-10-26 fixed at a0ed6304d (CI green there, 25/25 upstream).

Next:
- Developer: answer the 3 cram2#804 threads (fixed, outdated, unresolved).
- #202 must adopt this layer's unified names when it next merges main.
