## shape-vocabulary-on-main (montessori-perception-split, layer 2) - draft #488

Layer = verbatim files of #202 (montessori_perception_on_main), re-cut after every #202 change.
Work happens in the /home/user/wt202 worktree; tests: PYTHONPATH=$(ls -d /home/user/wt202/*/src | tr '\n' ':')
pytest --noconftest.

Plan:
- Land the layer once the developer is happy with the KnownPiece replacement and CI is green.

Done:
- #488 = #202 at 3b1beec32 (823fef2a0, 14 files, 78 passed). #202: 227 passed, 1 skipped.
- KnownPiece replaced by PieceSet worlds of bodies (full_size; smaller from #265). The 40 mm hole is the
  sphere's. The world copies the measured pieces. The insertion pose turns a piece onto its hole.
  GRID_ROUNDING was added to the matcher test (developer chose (a)).
- Replied on the KnownPiece thread and left it open (its EQL side is not done). Both descriptions updated.

Next:
- CI on #202 3b1beec32 and #488 823fef2a0 (not polled; ORM mapping of PieceSet/PieceOutline unverified here).
- The developer's answer on the open KnownPiece thread: do the EQL observation query, or close it.
- Sim insertion now has only real clearance (1 mm/side for the cube); the physics demos were not run here.
