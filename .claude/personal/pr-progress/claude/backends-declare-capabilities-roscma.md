# backends-declare-their-capabilities (icra-mechanism), PR #303

Base: `claude/icra-experiments-simulation-pipeline-w4ep7n` (#265), not `tracy_icra` — same
precedent as `snapshot-working-memory` (#301): `tracy_icra` doesn't carry #265's content yet
(checked via `git merge-base --is-ancestor`), and this item needs `PerceptionDetector.capability`,
`DetectorChoice`, `AttributeEqualityToLiteral.read_from` and `QueryBackend`, all on #265.

## Plan

1. `QueryBackend.capability(self, thing: Selectable) -> ConditionType` — same shape as
   `PerceptionDetector.capability(look)`, but not making `QueryBackend` generic over one bound
   type: a backend answers many classes, so the generalization is in the method signature
   (any `Selectable`), not in a type parameter on the class.
2. Field-level capability: name a specific field of a specific class via EQL `Attribute`/
   `MappedVariable`, read back the way `AttributeEqualityToLiteral.read_from` already reads an
   attribute equality — not a field-name string.
3. The underspecified-description helper: given `a(SomeClass)` naming only a class, add the
   features the twin already knows about that class to the description before a backend is
   chosen (the developer's own example: `a(MontessoriBoard)`). Nothing does this today.
4. Declare capability for every backend already in the tree (`EntityQueryLanguageBackend`,
   `SQLAlchemyBackend`, `EntityQueryLanguageGenerativeBackend`, `ProbabilisticBackend`,
   `PerceptionBackend`) — not physics/motion-statechart/VLM, which don't exist yet and are
   later items' work.
5. Tests: one declaration per backend against a statement it accepts and one it refuses,
   as a `krrood`-only mimic dataset (`test/krrood_test/dataset/`), following
   `detectors_that_state_what_they_answer.py`'s pattern.

Full reasoning and the amendment history: `icra-mechanism/roadmap.md`'s 2026-09-09 kickoff
section.

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

## Next

- Implement the plan above, tests first.
