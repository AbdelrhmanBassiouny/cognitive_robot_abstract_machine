# `montessori-classes-in-the-orm` — PR #223 (draft), off #202

Plan item `montessori-classes-in-the-orm` of `knowledge-directed-perception`,
track `package-landing`. Base `montessori_perception_on_main` (#202, `open_ready`).
Kicked off in `auto` mode 2026-08-30.

## The plan

1. `test/experiments_test/test_montessori_orm.py`, written first — three behaviours:
   - the package walk offers the Montessori classes to the generator;
   - no Montessori class shares its name with one `semantic_digital_twin` maps;
   - `get_dao_class(CubeShape)` resolves against the generated interface.
2. `experiments/src/experiments/montessori/__init__.py`, empty, like `perception/__init__.py`.
3. Rename `perception.footprint.Footprint` → `RectifiedFootprint` (footprint.py,
   detections.py, pipeline.py, test_montessori_footprint.py, docstrings).
4. `scripts/format_docstrings.py` over every modified file.

## Established before writing anything

- `classes_of_package(experiments)`: **87** classes on the parent, **154** with the
  `__init__.py`. That is the whole cause.
- The duplicate `FootprintDAO` reproduces: importing the generated interface raises
  `InvalidRequestError: Table 'FootprintDAO' is already defined for this MetaData instance`.
- `NoSceneAvailable.missing_inputs: Sequence[str]` **resolves** — ORMatic normalizes it to
  `typing.List[builtins.str]`, mapped as JSON. The item's note was wrong about this; no
  change is made for it.
- Nothing else was behind those two.

## Environment

`uv sync --extra dev --python 3.12` builds the whole workspace; everything imports.
#216's hand-built recipe is obsolete. But the full ORM regeneration still cannot run:
`giskardpy`'s generator raises `CouldNotResolveType: DebugExpressionPublisher` and
`coraplex`'s imports `geometry_msgs` — both on the *unmodified parent*. Verification
therefore runs against a probe that builds the experiments class diagram with the
`semantic_digital_twin` and `giskardpy` interfaces as dependencies
(`scratchpad/experiments_diagram_probe.py`, plus `giskardpy_generate_orm_without_ros.py`
to get giskardpy's interface built at all). Scratch harnesses, not repository changes.

## Done — the item is built, `08a6513e3`

- Branch cut off #202, draft PR #223 opened, manifest and roadmap recorded.
- Three tests written first; all three failed on the parent, each for its own reason.
- `experiments/montessori/__init__.py` added; `Footprint` → `RectifiedFootprint` across
  `footprint.py`, `detections.py`, `pipeline.py` and `test_montessori_footprint.py`.
- Probe rebuilt: one `RectifiedFootprintDAO`, the interface imports, and `get_dao_class`
  resolves `CubeShapeDAO`, `MontessoriShapeDAO`, `ShapeSortingBoardDAO`,
  `ShapeSortingHoleDAO`.
- `145 passed, 1 skipped` across the eleven `test_montessori_*` modules, against
  `142 passed, 1 skipped` on the parent — the three added and nothing else.
- PR description updated to match; dashboard republished; tracking issue told.

## CI, 2026-08-30

`experiments` passed: **321 passed** against **318** on #202 — the three added tests and
nothing else. That job regenerates the interfaces through the conftest, so the DAO test ran
against a real generated `experiments/orm/ormatic_interface.py` with coraplex in the chain,
which is the one thing the container could not do. The ORM fix is confirmed in CI.

Two of 23 red, neither reachable by this diff:

- `test_each_lib (giskardpy)` — `test_integration_pr2.py::TestSelfCollisionAvoidance::
  test_attached_self_collision_avoid_stick`, one AssertionError against 516 passed. A PR2
  motion-statechart/QP integration test; `giskardpy` neither imports nor maps `experiments`.
- `test_each_lib (coraplex/scripts/test_notebook_examples.sh)` — `RuntimeError: Kernel died
  before replying to kernel_info`, i.e. the kernel never started. That job runs `treon`, no
  pytest, so no conftest and no ORM regeneration at all.

Both are green on the base #202 and on sibling #222, whose run started 13 minutes later on
the same infrastructure. Failed jobs of runs 33337224858 and 33337224869 re-run once at the
developer's prompting; the outcome is the deciding evidence and is not yet in.

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
