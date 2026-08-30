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

## Next

- Nothing on this branch. It is a draft awaiting review.
- When #205 or #221 rebases, the rename conflicts in `pipeline.py`/`footprint.py`:
  take their edit, spell the class `RectifiedFootprint`.
- The DAO test runs for real only in CI, where the conftest builds the interface.

## Watch out

- #205 and #221 are editing `pipeline.py`/`footprint.py` right now. Every renamed line is a
  conflict they inherit — keep the rename to the one identifier.
- Do not re-draft #202 or touch it; its out-of-draft state is a recorded decision.
