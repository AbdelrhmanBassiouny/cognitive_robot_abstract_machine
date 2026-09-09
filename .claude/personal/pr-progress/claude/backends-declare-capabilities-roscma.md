# backends-declare-their-capabilities (icra-mechanism), PR #303

Base: `claude/icra-experiments-simulation-pipeline-w4ep7n` (#265), not `tracy_icra` — same
precedent as `snapshot-working-memory` (#301): `tracy_icra` doesn't carry #265's content yet
(checked via `git merge-base --is-ancestor`), and this item needs `PerceptionDetector.capability`,
`DetectorChoice`, `AttributeEqualityToLiteral.read_from` and `QueryBackend`, all on #265.

## Plan — as implemented (corrected from the kickoff sketch)

1. `QueryBackend.capability(self, statement: Evaluable) -> ConditionType` — takes the
   whole statement (same object `evaluate()` is put), not one bound type parameter:
   a backend answers many classes, so the generalization is in the method signature.
2. Field-level capability: `backend_supplies(backend, field: Attribute) -> bool`, built
   on top of `capability()` rather than beside it — wraps the field into an
   otherwise-underspecified statement over its own class and asks `capability()`.
3. The underspecified-description-fill helper — **not built**. Deferred: genuinely new
   per the item's own notes, and "the model" it should read from isn't settled by
   anything checked this session (a candidate, `ModelRegistry`, is unconfirmed).
4. Declared capability for every backend already in the tree: `SelectiveBackend`/
   `GenerativeBackend` base conditions (inherited by `EntityQueryLanguageBackend`/
   `PerceptionBackend` unchanged), plus narrower ones on `SQLAlchemyBackend`,
   `EntityQueryLanguageGenerativeBackend`, `ProbabilisticBackend`, and — found via a
   repo-wide grep for every other `QueryBackend` subclass — `RDRBackend`.
5. Tests directly against the real backend classes (all live in `krrood` itself, unlike
   the real perception detectors), not a mimic dataset as first sketched:
   `test/krrood_test/test_eql/test_backend_capabilities.py` (15 tests) +
   `test_rdr_backend.py` (4 new tests).

Full reasoning, the amendment history, and the `RDRBackend` finding:
`icra-mechanism/roadmap.md`'s 2026-09-09 sections.

## Found, not fixed here

`plan_item_bootstrap.py`'s `apply_item_fields` hardcodes 4-space field indent / 2-space item
marker (matching `plans/README.md`'s schema example), but every actual `plan.yaml` in this repo
uses 0-indent markers with 2-space fields — patching or inserting a field through the script
corrupts the manifest. Worked around by hand-patching this item's fields at the file's real
indent and pushing directly; not fixed here (shared tooling on `main`, out of this item's scope).
Worth a `plan-tracking-skills` item — every kickoff/resolve that patches or inserts a field on
any plan is exposed until it is.

## Done

- Branch re-cut from `claude/icra-experiments-simulation-pipeline-w4ep7n` (was an unmodified
  copy of `integration`, which is not a valid PR base).
- Draft PR #303 opened.
- `plan.yaml`/`roadmap.md` updated (item now `in_progress`, branch/PR#/session recorded).
- `capability()` mechanism + declarations implemented and tested (see Plan above).
- Built a scoped krrood-only test venv (`/tmp/krrood-venv`, this container has no
  `.venv`/`uv`-buildable workspace out of the box — the root `pyproject.toml` has a
  pre-existing TOML syntax error blocking any `uv` install, worked around with plain
  `pip`; `random_events`/`probabilistic_model` installed from this repo's own local
  copies, not PyPI, since PyPI's `probabilistic_model` lacks a submodule this tree
  imports). Full `test/krrood_test` suite verified clean: 2731 passed, 7 skipped, 0
  failed (3 modules excluded from collection for reasons unrelated to this change —
  missing `mypy`, no `dot`/Graphviz binary, a rustworkx-visualization import gap — all
  confirmed pre-existing).
- PR description and test-plan checklist updated to match.

## Next

- Nothing outstanding for this PR's own scope. The deferred helper (item 3 above) is a
  follow-up, not blocking — recorded in the roadmap and the PR description.
