## shape-vocabulary-on-main (montessori-perception-split, layer 2) - draft #488

Cut from #202 at 6dda1916e (was 4653fe32e); branch off main 236b295a2.

Done:
- Kickoff: bootstrap 5e1856058, layer 1fc3188fb, draft PR, manifest, roadmap, dashboard.
- Review 2026-10-04 (9 threads): the developer chose to answer it on #202 and then re-cut.
  - 6dda1916e on montessori_perception_on_main changes every caller on #202:
    - enum removed in favour of the MontessoriShape classes;
    - HoleShapeClassifier, ShapeSortingBoardMesh and HoleFootprint.MARKER_THICKNESS;
    - PieceHue, HueCircle and PieceSet.this_lab();
    - Point2 and PlanarBoundingBox reused, and Polygon2D added to SemDT geometry.py with test_polygon.py;
    - pieces-only tests moved into test_montessori_pieces.py.
    - Tests: 174 passed, 1 skipped with --noconftest via the /home/user/wt202 worktree and PYTHONPATH.
  - 2f0358c7b re-cuts #488: 10 files byte-identical to 6dda1916e; 45 passed on the branch alone.
  - Replied on all 9 threads and resolved 8. The SemDT thread stays open on whether HueCircle belongs in SemDT.
  - #488 and #202 descriptions updated. #488 stays a draft. #202 was already ready before this push and was left as it was.
  - Plan notes and roadmap saved (5bc27b51c).

Next: CI on 6dda1916e (#202) and 2f0358c7b (#488) - not polled; ORM mapping of the new dataclasses is only
checkable in CI. The developer's answer on the HueCircle thread. Downstream branches of #202 need a merge.
