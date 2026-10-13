## shape-vocabulary-on-main (montessori-perception-split, layer 2) - draft #488

Layer = verbatim files of #202 (montessori_perception_on_main), re-cut after every #202 change.
Work happens in the /home/user/wt202 worktree; tests: PYTHONPATH=$(ls -d /home/user/wt202/*/src | tr '\n' ':')
pytest --noconftest.

Plan:
- Replace KnownPiece with real SemDT bodies (developer's review on pieces.py:203); #488 is blocked until done.

Done:
- #488 = #202 at 83019e34d (13b021da8, 14 files). Pushed on #202: d4abc697d (Pose properties),
  be578659e (Hue in Color), d350dabb3 (DetectionColor -> Color), 83019e34d (footprint, symmetry).
- LOCAL, UNPUSHED on #202's branch:
  - d85a50a2b: PieceSet = world of bodies (full_size; smaller from #265 at x0.8 with hues 196/52 deg);
    KnownPiece removed; matcher uses PieceOutline.
  - d96eee1082: the 40 mm round hole is the sphere's (both classifiers, 36 mm threshold); the world copies
    the measured pieces in their own orientation; the insertion pose turns a piece onto its hole
    (Polygon2D.turn_onto).
- 226 passed, 1 skipped, 1 failed.

Next:
- Developer's call on the failing triangle "found where it stands" test (OBJ rounding; options a/b/c).
- Then push #202, re-cut #488 (adds hole_geometry.py, semantics.py changes), and update both descriptions.
- Reply on the KnownPiece thread; consider unblocking #488.
