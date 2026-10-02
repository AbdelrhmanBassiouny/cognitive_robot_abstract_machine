## shape-vocabulary-on-main (montessori-perception-split, layer 2) - draft #488

Plan:
1. Check out verbatim from #202 tip 4653fe32e: montessori/{semantics,exceptions,hole_geometry,pieces}.py,
   resources/board.stl, test_montessori_semantics.py, test_montessori_hole_geometry.py.
2. New test_montessori_pieces.py: the 3 pieces-only colour tests moved verbatim out of
   test_montessori_piece_matching.py (the 2 SurfaceColors tests + _painted stay for 5b).
3. Commit with Co-authored-by: sorinar329 <mrsoran2009@gmail.com>.
4. Verify: tests pass on this branch alone (--noconftest); imports resolve against main.
5. PR description, mark manifest, republish dashboard.

Done: bootstrap commit, draft PR #488, manifest open+record, roadmap section.
Next: step 1.
Flag recorded in roadmap: test move means final merge into #202 is not file-neutral for test files.
