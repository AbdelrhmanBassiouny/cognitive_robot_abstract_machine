## shape-vocabulary-on-main (montessori-perception-split, layer 2) - draft #488

Layer = verbatim files of #202 (montessori_perception_on_main), re-cut after every #202 change.
Work happens in the /home/user/wt202 worktree; tests: PYTHONPATH=$(ls -d /home/user/wt202/*/src | tr '\n' ':')
.venv/bin/python -m pytest --noconftest. Format with the venv's bin on PATH (docformatter).

Plan:
- Land the layer once the developer is happy with the KnownPiece replacement and CI is green.

Done:
- #488 = #202 at 136ea6888 (ab39a37e7, 14 files, 79 passed). #202 montessori tests: 65 passed, 1 skipped.
- hole_for finds a shape's hole by fit alone (name preference removed); that thread is resolved.
- Answered the partial-description question on the KnownPiece thread: #265 has EQL look requests,
  not observation-vs-PieceSet matching. #265 is an integration branch (never merged; extract from
  it), so that work would be its own PR extracting LookRequest/PerceptionBackend. Thread left open.

Next:
- CI on #202 136ea6888 and #488 ab39a37e7 (not polled; ORM mapping of PieceSet unverified here).
- The developer's answer on the KnownPiece thread: a separate item for EQL observation matching, or close it.
- Sim insertion now has only real clearance (1 mm/side for the cube); the physics demos were not run here.
