## Next
- Read the two re-run results. If both pass, the branch is green and nothing else is owed.
  If either reproduces identically, say so on the PR rather than silently — it is still not
  this branch's failure, and the re-run is spent.
- Otherwise nothing on this branch. It is a draft awaiting review.
- When #205 or #221 rebases, the rename conflicts in `pipeline.py`/`footprint.py`:
  take their edit, spell the class `RectifiedFootprint`.
- The DAO test runs for real only in CI, where the conftest builds the interface.


## Watch out
- #205 and #221 are editing `pipeline.py`/`footprint.py` right now. Every renamed line is a
  conflict they inherit — keep the rename to the one identifier.
- Do not re-draft #202 or touch it; its out-of-draft state is a recorded decision.

## The plan
1. `test/experiments_test/test_montessori_orm.py`, written first — three behaviours:
   - the package walk offers the Montessori classes to the generator;
   - no Montessori class shares its name with one `semantic_digital_twin` maps;
   - `get_dao_class(CubeShape)` resolves against the generated interface.
2. `experiments/src/experiments/montessori/__init__.py`, empty, like `perception/__init__.py`.
3. Rename `perception.footprint.Footprint` → `RectifiedFootprint` (footprint.py,
   detections.py, pipeline.py, test_montessori_footprint.py, docstrings).
4. `scripts/format_docstrings.py` over every modified file.
