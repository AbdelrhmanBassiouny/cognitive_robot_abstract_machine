# eql-verbalization — roadmap & rationale

Cross-PR roadmap for the semantic_digital_twin verbalization review on PR #33. Migrated out of
`cram-notes.md`'s "EQL verbalization follow-up plan" living-roadmap section (2026-07-29), which
had grown into the single largest recurring per-session token cost across every branch — see
`plans/workflow-unification/roadmap.md`'s "Why this plan exists" for the review that identified
it. #32 (SymbolicFunction migration) and P1–P3 (#86, #87, #88) are all merged to `main`. P4 (sdt
= PR #33) is the last of the original four; P5 was split out of P4's review on 2026-07-30.

## Finalized design decisions

1. Operand naming: grammatical metadata on the field → field/attribute name → type name
   (last resort). Provide the metadata mechanism with good defaults (low modelling
   burden); build on the existing `_attribute_name_` / possessive / referring
   microplanning. (Replaces "always the type name", which read awkwardly, e.g. "Point3".)
2. Same-type operands: determiners ("a point … the other point"), not numbering ("Point3 1/2").
3. Value-agnostic (first-order) + value-using forms, and abstract→concrete-subclass
   expansion ("a Body or a Region"): their own phase (P3), on `concrete_subclasses` +
   `RoleFragment.for_type` / `for_literal`.
4. Fragments must use `Noun` / `Noun.bare` / `Noun.the`, never a raw `WordFragment`.
5. `EuclideanPlanarDistance`: `custom_relation` with `Prepositions.BETWEEN`, not `of`.
6. `Pose` type hints (predicates.py:292, robot_predicates.py:158 are
   HomogeneousTransformationMatrix): investigate and switch to `Pose` if correct/clearer.
7. No abbreviations (`cm`→`collision_manager`); sweep all touched code.
8. Keep the functional wrapper name `get_volume` (the class stays `AnnotationVolume`).
9. ormatic `type`-mappability PR: DROPPED (maintainer), so excluding `SymbolicCallable`
   subclasses from ORM generation is the surviving path for P4's `ClassNameLowercased`.
   Superseded 2026-07-30: `OPERAND_OVERRIDES` no longer exists — P3 replaced it with the
   `SymbolicCallable._example_operand_values_` class hook, which the snapshot consults per
   class. An override belongs on the class, not in a test-side dict.
10. Keep surfaces concise (omit root/tip from `BlockingBodies`); details are query-able.
11. `Reachable` reads *"a Pose is reachable for the kinematic chain rooted at <root> and
    ending at <tip>"* — the chain is what reaches, and root/tip stay named here (unlike
    `BlockingBodies` under decision 10) because reachability is only meaningful relative
    to them.
12. Naming a referent by value *and* type on first mention (*"a gripper of type
    HasTwoFingers"*) is out of P4's scope — it is coreference behaviour, not an sdt
    wording, and is tracked as its own item (`p5-first-mention-type-annotation`).

## Standing conventions — every session on this plan must

- Critically evaluate first: don't blindly implement; assess vs this codebase's
  verbalization/EQL architecture, the literature (NLG surface realization, grammar
  frameworks, snapshot testing), and reliability/scalability/maintainability + SOLID.
  Surface a better approach or a flaw and discuss before implementing.
- Follow AGENTS.md incl. Version Control (commit as the human identity, no assistant
  trailers, "Made with the help of Claude." note allowed), no abbreviations, dataclasses,
  absolute/top-level imports, RST field docstrings, no `getattr`, guard clauses, SOLID,
  TDD, black+docformatter (`scripts/format_docstrings.py`).
- The exhaustive `SymbolicSurfaceSnapshot` test (now `VerbalizationResultsOfPackage`, see
  P1's item note) is the coverage mechanism; keep it green.
- To render sdt/coraplex surfaces locally: build random_events (`pip install ./random_events`
  → gives native `random_events_lib.reals`), `pip install trimesh mujoco daqp plyfile lxml`,
  PYTHONPATH = krrood/src + <pkg>/src + giskardpy/src + probabilistic_model/src +
  coraplex/src + repo root, and stub `giskardpy_bullet_bindings` (MagicMock in sys.modules)
  before importing — rendering needs type names, not physics. CI has the real stack; commit
  no env hacks.

## P1–P3 status

All three merged to `main`; see `plan.yaml`'s item notes for a one-line summary of each and
`.claude/personal/pr-progress/<branch>.md` for the full review-round history — that file, not
this roadmap, is the source of truth for their per-PR detail (`plans/README.md`'s convention).

## P4 — sdt migration

PR #33 (`eql-symbolic-function-sdt`, base `main`), open and draft. As of its last push
(2026-07-18) `mergeable_state` was `dirty` — it predates P1/P2/P3 all merging to `main`, so it
needs a rebase (dropping the now-upstreamed surface-verification framework it still carries a
duplicate of) before any checklist item below can start.

### P4 sdt checklist (reasoning/predicates.py, queries.py, robot_predicates.py; test snapshot)

- Reachable: remove `fields["tip"].name`; reword per decision 11; Pose hint (dec 6).
- No abbreviations sweep (dec 7); `Noun`/`Noun.bare`/`Noun.the` not raw `WordFragment` (dec 4).
- get_volume wrapper name kept (dec 8).
- Wordings: GetVisibleBodies "the bodies visible to/through a camera"; EuclideanPlanarDistance
  `between` (dec 5); IsSupportedBy "a body is supported by another body" (drop threshold);
  IsPlaceOccupied custom "a place represented by a bounding box at a given pose is occupied by
  other bodies in the world"; InFrontOf/Above/Below/LeftOf/RightOf/Behind "a point is in front
  of the other point"; OccludingBodies "the bodies that occlude another body from the view of a
  camera"; Visible value-agnostic + concrete subclasses; BlockingBodies "the bodies blocking the
  path to reach a pose" (concise); IsGripperHoldingSomething "a gripper is holding something";
  BodyInGripperFraction "the part of the body between the fingers of the gripper"; BodiesInGripper
  "the bodies between the fingers of a gripper"; RobotCollisions "the collision points between a
  robot and the bodies of the world"; ClassNameLowercased "the lower case form of a class name";
  AnnotationVolume "the volume of a <concrete annotation type>".
- Wire the sdt snapshot to the generator; reply-and-resolve each review thread.

### How the snapshot works now (corrected 2026-07-30)

The snapshot module is *generated*, not hand-written — the hand-written `SURFACES` tuple
PR #33 still carries is the wrong shape. `krrood/.../testing/result_generation.py`'s
`regenerate_verbalization_results` is called from a package's own `conftest.py`
(`test/krrood_test/conftest.py` is the reference) so the module is rebuilt every test run
and an intentional wording change lands as an ordinary diff to review. Verification is
`VerbalizationResultsOfPackage` in `krrood/.../testing/result_verification.py`, with two
asserts — `assert_results_cover_every_callable` and
`assert_declared_results_render_as_stated`. So P4's snapshot work is adding the
regeneration call to `test/semantic_digital_twin_test/conftest.py` plus the two-assert
test, not editing a committed tuple.

## P5 — first-mention type annotation (split out of P4, 2026-07-30)

From PR #33's `BodiesInGripper` thread: *"maybe one can mention both the name and the
type … but that would maybe only make sense for the first introduction of the variable in
the whole verbalized statement."* Confirmed out of P4's scope — it is coreference
behaviour belonging to the `ReferringExpressions` machinery P2 built, so it applies to
every package's surfaces at once rather than to sdt's wordings. P4 renders
*"the bodies between the fingers of a gripper"* and this item takes the type annotation
on separately.

## P4 progress (2026-07-30)

Merged `main` into #33 and did the whole checklist; see
`pr-progress/eql-symbolic-function-sdt.md` for the per-step account. Two findings that
change the roadmap rather than just the PR:

- **Decision 1 is inverted from what P2 shipped.** It records "grammatical metadata on the
  field → field/attribute name → type name (last resort)". `operand_head_noun`
  (`verbalization/microplanning/referring.py:193`) does the opposite: a concrete type's noun
  always wins, and `display_name`/field name are consulted *only* when the type is the
  uninformative `object`. The docstring argues for it deliberately, citing the Incremental
  Algorithm. So *"a Point3"* → *"a point"* is not reachable from a field-side override at
  all; it needs a type-level display noun (the natural home is `value_lexicon.type_noun`,
  which today special-cases only primitives). Left as an open thread on #33 with three
  options for the user; do not "fix" decision 1 either way without that answer.
- **Value wordings needed a new vocabulary builder.** Several reviewed sentences name the
  value with a phrase of its own (*"the bodies visible to a camera"*) rather than a reading
  of the class name, which is all `FunctionVerbalizationTemplates` can express. Added
  `phrase()` as the value counterpart of `clause()`. Decision 4 (`Noun` over raw
  `WordFragment`) is what rules out the alternative, so treat `phrase()` as the sanctioned
  way to satisfy both from here on.

## P4's `predicates.py` half was built elsewhere, and P4 rebases onto it (2026-08-31)

`knowledge-directed-perception`'s item `predicates-answer-whether-they-hold` (#229,
`sdt_predicates_answer_whether_they_hold`, off `main`) migrated `reasoning/predicates.py`
off `@symbolic_function` onto `Predicate` / `SymbolicFunction` classes by the same
`symbolic_callable_to_function` mechanism P4 uses - independently, and without either
plan's manifest naming the other. Every relation P4 converted in that file, #229 had
converted too; both even write `reachable = symbolic_callable_to_function(Reachable)` over
the same class body.

**The developer settled it in #229's favour on 2026-08-31: #229 carries the predicate
classes, and P4 rebases onto the `main` that has them** - dropping its own copy of the
`predicates.py` migration and re-applying its 34 reviewed wordings onto #229's classes.
The reasoning was about which rebase is cheaper: this branch is 166 commits behind `main`,
`dirty` in `predicates.py` specifically and labelled `needs-resolution`, so it owes that
rebase either way and meets #229's version of the file whichever order the two land in;
while P4's two open decisions block it and do not block #229, whose plan has a 2026-09-15
deadline.

**Nothing else of P4's is affected.** `queries.py`, `robot_predicates.py`, `phrase()` in
krrood's `parts_of_speech`, `ORMatic.from_package(ignored_base_classes=...)` and the
generated verbalization snapshot wired into sdt's `conftest.py` are all still this item's,
and #229 touches none of them. The snapshot in particular is worth landing: sdt has no
verbalization test on `main`, which is exactly why #229 shipped four ungrammatical
sentences before anyone read them.

**Two wordings are already carried across on #229**, and one of them needs a decision here:

- The four relations #229 named for their object (`SupportedBy`, `VisibleTo`,
  `InContactWith`, `Supports`) took P4's own reviewed sentences - *"is supported by"*,
  *"is visible to"*, *"is in contact with"*, *"is supporting a body"* - rather than a third
  set. `Visible` reads *"visible **to**"* there against P4's *"visible **from**"*, following
  the class name `VisibleTo`.
- `Reachable` reads *"a Pose is reachable by a Tip"* on #229, which is what the developer
  asked for on that pull request (r3896606294). **Decision 11 words the same relation *"a
  Pose is reachable for the kinematic chain rooted at <root> and ending at <tip>"***. Both
  make the pose the subject and differ only in whether both ends of the chain are named;
  the thread is deliberately left open on #229 for the developer to pick which stands, and
  whichever he picks is what this rebase should apply.

Worth carrying into the rebase: `Triple` derives its verb from the class name, so a
relation named for its object must state its own clause - inheriting `Triple` and saying
nothing is what produced *"a Body supports by another Body"* on #229.
