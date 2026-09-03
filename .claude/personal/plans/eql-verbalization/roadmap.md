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
11. `Reachable` reads *"a Pose is reachable for the kinematic chain rooted at `<root>` and
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
  Pose is reachable for the kinematic chain rooted at `<root>` and ending at `<tip>`"***. Both
  make the pose the subject and differ only in whether both ends of the chain are named;
  the thread is deliberately left open on #229 for the developer to pick which stands, and
  whichever he picks is what this rebase should apply.

Worth carrying into the rebase: `Triple` derives its verb from the class name, so a
relation named for its object must state its own clause - inheriting `Triple` and saying
nothing is what produced *"a Body supports by another Body"* on #229.

## New item: aggregate-repeat-reduction-ignores-same-kind-siblings (2026-09-02)

Found on `match-query-ergonomics`'s PR #196 (`aggregate-signature-reads-a-missing-attribute`)
during its self-review round: the developer flagged the closing assert of
`test_ranking_names_the_ordered_by_aggregate_not_the_first_selected`
(`test_set_of_ranking.py:337`), proposing the trailing bare *"the sum"* be spelled out in
full as *"the sum of the amount of its tax"*.

**Measured, not guessed at.** All 17 tests in the file pass as written, including this one:
`tax` is the literal same object in both the ranking frame (`.ordered_by(tax, ...)`) and the
selection, so `AggregatorRule.build`'s coreference (`referent_id=node._id_` in
`verbalization/grammar/aggregation/rules.py`) resolves the trailing *"the sum"* back to the
frame's `tax` mention by identity — exactly what `_highest_aggregate_modifier`'s docstring
says it should do. #196's own fix (`_expression_signature` reading `_child_` instead of the
undefined `_chain_expression_`) is what makes that resolution *correct* in the first place;
it is not the same bug.

**The concern is real independent of code correctness.** To a reader, *"the sum of the
amount of its net, and the sum"* reads as though the trailing *"the sum"* refers to the
noun phrase right before it (`net`) — proximity is how anaphora normally resolves, and the
`tax` antecedent is three clauses back in the ranking frame. That ambiguity only surfaces
once two aggregates of *one kind* are both selected, which is exactly the case #196 adds
coverage for.

**The developer's follow-up** (PR #196, review thread
[r3919032569](https://github.com/AbdelrhmanBassiouny/cognitive_robot_abstract_machine/pull/196#discussion_r3919032569)):
*"ok make fixing it an item of its own, I am unsure though if this should be in
match-query-ergonomics or another plan or a new plan."*

**Placement, via `/add-plan-item`.** `check_scope_overlap.py` against every open pull
request whose changed paths could plausibly touch this (`match-underscore-rename-and-forwarding`
#192, `chain-signature-reads-attribute-only-names` #248, `p4-sdt-migration` #33) over
`verbalization/grammar/aggregation/rules.py`, `verbalization/rendering/coreference_processor.py`
and `verbalization/microplanning/referring.py` reports no shared paths and no duplicate
intent — nothing unlanded already owns this. Between the three candidates the skill's
step 5 offers (fold into `match-query-ergonomics`, new item here, or a new plan of its own),
put to the developer via `AskUserQuestion` with the evidence for each: `eql-verbalization`
was chosen. The bug lives in `CoreferenceProcessor`/`DistinguisherIndex` — the *"same-noun-group
disambiguation (`'another Robot'`, `'a second Robot'`)"* machinery P2 built, per that class's
own docstring — not in the underscore-naming convention `match-query-ergonomics` is
refactoring; the connection to #196 is only "found while extending its test coverage," not a
shared root cause. `p5-first-mention-type-annotation` already sits in this exact track for an
analogous refinement of the same machinery ("belongs in the ReferringExpressions/coreference
machinery P2 built, not in any one package's ... wordings" — decision 12 / P5's own item
note), which is the precedent this new item follows: `track: framework-migration`,
`depends_on: [p2-operand-naming]` (merged), `status: not_started`.

**Not designed yet, only measured.** The fix likely means `AggregatorRule.build`'s reduction
(or the coreference pass that consumes its `referent_id`) needs to know when an identity
match is one of several same-kind aggregates in the current scope, and spell the repeat
mention out in full in that case rather than reducing on identity alone — but whether that
belongs in `AggregatorRule.build`, in `CoreferenceProcessor`, or in `DistinguisherIndex`
itself is an open question for whoever picks this item up.

Replied on PR #196's thread with this outcome and resolved it, since the developer's ask —
*"make fixing it an item of its own"* — is now done.

## P4's rebase is waiting on #229, which has not merged (2026-09-03)

The 2026-08-31 decision above — *#229 carries the predicate classes and P4 rebases onto the
`main` that has them* — recorded the outcome but not the precondition, so the item read as
actionable when it is not. As of 2026-09-03, **#229 is still open and unmerged**: state
`open`, out of draft, `mergeable_state: clean`, base sha `fd72af38`, which is `main`'s own
current tip. `main`'s `reasoning/predicates.py` therefore still carries the twelve
`@symbolic_function` helpers and the `Symbol`-derived spatial relations. There is no `main`
with #229's classes to rebase onto yet.

**And P4's own test is what makes waiting compulsory rather than merely tidy.**
`test_every_symbolic_callable_declares_its_own_verbalization_fragment` asserts that every
symbolic callable discovered in sdt implements its own `_verbalization_fragment_` — the test
that exists precisely so a new `@symbolic_function` from `main` cannot merge in unnoticed
(it is what caught `is_body_gripped` in round 4). Taking `main`'s `predicates.py` today
would import a dozen callables with no fragment of their own and turn that test red. So
dropping this branch's copy early is not an option: the drop and #229's landing are one
step, not two.

**What is separable is the conflict.** `git merge-tree` puts the entire collision in
`predicates.py` and nothing else — `ormatic.py`, `generate_orm.py`, `queries.py`,
`robot_predicates.py` and the test files all auto-merge. `main`'s delta to that file since
the merge base is three real changes and nothing structural: `camera.root_T_forward_view`
plus an explicit `field_of_view` in `get_visible_bodies` and `occluding_bodies`, and
`BoundingBox` -> `VolumetricBoundingBox` in `is_place_occupied`. Porting those three into
this branch's migrated classes clears `needs-resolution`, stops a routine that has
re-reported the same conflict ten times in a week, and lets CI run again on a branch whose
last run was 2026-08-24 — while costing only work that #229's landing will supersede anyway.

**The `Reachable` wording is settled, by a resolve rather than a sentence.** #229's thread
r3896606294 asked for *"Pose Is reachable by Tip"*; the reply offered decision 11's longer
*"a Pose is reachable for the kinematic chain rooted at `<root>` and ending at `<tip>`"* and left
the thread open for the developer to pick. That thread now reads resolved on #229, where the
shorter wording stands — so decision 11 is superseded to that extent, read from the resolve
rather than stated outright.

**A third review thread was open all along and unrecorded.** The item's blockers said two
decisions; #33 actually has nine unresolved threads, which are three distinct questions once
the six same-comment repeats of the type-noun thread are collapsed. The third is
`ClassNameLowercased`: it renders *"the lower case form of the name of a type"* rather than
the reviewer's literal *"the lower case form of a class name"*, deliberately, to keep the
operand in the sentence — offered as a choice (r3608403117) and never answered. It blocks
nothing and needs one word from the developer.

## aggregate-repeat-reduction: the settled plan (2026-09-03, PR #264)

Kicked off in `auto` mode on `claude/eql-verbalization-aggregate-repeat-gdz9g2`, cut from
`main` (its only dependency, `p2-operand-naming` / #87, is merged, so nothing else gates it).

**The symptom, re-measured on `main` rather than taken from #196.** Two manifestations,
both from one cause:

- ranked (`ordered_by(...).limit(1)`): *"For the Invoice with the highest sum of the amount
  of its net, report the month of the begin of its period, **the sum**, and the sum of the
  amount of its tax"*
- ordered (`ordered_by(...)`, no limit): *"For each month, report the sum of the amount of
  the net of an Invoice and the sum of the amount of its tax ordered by **the sum** from
  highest to lowest"*

So this reproduces without #196 — that pull request decides *which* of the two sums the
ranking frame names, not whether the shortened mention is ambiguous. Worth recording,
because the item's own note describes the symptom in #196's wording and could be read as
making it a prerequisite.

**Design, and why it is not an open question.** The developer already said on #196's thread
(r3919032569, quoted in this roadmap's "New item" section) that the trailing bare *"the
sum"* should be *spelled out in full*. That rules out the alternative the item's note left
on the table — registering aggregates in `DistinguisherIndex` so they read *"another sum"* /
*"the other sum"*. It is also the better answer on its own terms: an aggregate is told apart
by *what it aggregates*, not by a determiner, and *"the other sum of the amount of its tax"*
is worse than the full description it replaces.

**Where it goes.** `AggregatorRule.build` is what opts an aggregate into repeat-reduction, by
giving its noun phrase `referent_id=node._id_`; it is the same place to decide it must not.
The knowledge it needs — which aggregation words name more than one aggregate in the scanned
expression — is pre-scan referring-expression state, so it goes on `ReferringExpressions`,
which a rule already reaches through `RuleContext.refer`.

`CoreferenceProcessor` and `DistinguisherIndex` are deliberately untouched. A variable's
same-noun group *is* fully told apart by determiner (*"a Robot"* / *"another Robot"*), so its
reduced mentions stay identifying; a general "don't reduce when the noun is shared" guard
there would regress P2's design for the case P2 was built for.

**Distinctness is counted per aggregate node, not per structural signature.** Two `Sum`
objects over the same chain count as two. That is conservative, and a no-op in practice: two
such nodes carry different `_id_`s, so no repeat mention arises between them either way. The
alternative — structural comparison — is `_expression_signature` in `query/assembler.py`,
which #196 is currently changing, so reusing it would couple this branch to an unlanded one.

**Steps, tests first.**

1. The two end-to-end wordings above, asserted in full, plus a unit test of the new
   `ReferringExpressions` state. Planned for `test_set_of_ranking.py` and `test_coreference.py`;
   both moved into one new module during implementation, for the reason in the next section.
2. `microplanning/referring.py` — record which aggregations more than one aggregate is built from.
3. `grammar/aggregation/rules.py` — give the noun phrase a `referent_id` only when its
   aggregation names one aggregate.

Verification: `pytest test/krrood_test/test_eql/test_verbalization` (768 passed / 3 skipped
before the change), which includes `test_rule_doctests.py`, plus
`scripts/format_docstrings.py` on the modified files.

**Scope overlap: avoided rather than accepted.** The first draft of this plan put the tests in
`test_set_of_ranking.py`, which unlanded #196 is also appending to, and recorded the resulting
tail-of-file conflict as a cost to pay. Writing #196's added tests out showed the collision was
worse than that: it defines an `Invoice` mimic with exactly the fields this item needs
(`period`, `net`, `tax`), so the two branches would have defined the same fixture in the same
module. The tests therefore live in a module of their own,
`test_eql/test_verbalization/test_aggregate_reference.py`, named for the behaviour — how a
computed quantity is referred back to — rather than for `set_of` ranking, which is the file's
subject and not this one's. `check_scope_overlap.py --base origin/main` over the three files this
branch touches now reports no shared path with #196, #248, #192, #254 or #33.

**What shipped.** `ReferringExpressions.shared_aggregations` records the aggregations more than
one aggregate in the scanned expression is built from; `AggregatorRule.build` gives its noun
phrase a `referent_id` only when the aggregation names one aggregate, so an aggregate with a
same-word sibling is described in full at every mention. Six tests, written first and failing:
the two ambiguous wordings, the two cases that must still shorten (a lone sum; a sum beside an
average), and the pre-scan itself. `test_eql/test_verbalization` 768 -> 774 passed with 3 skipped
and no existing expectation changed; `test_eql` 1291 passed (`test_typing` needs `mypy`, absent
from this environment).

**Tooling note, not this item's work.** `plan_item_bootstrap.py open` could not record this
item: it writes `branch` / `pull_request_number` / `status` / `session` at a four-space indent
into a two-space manifest, so `save-plan.sh` fails in `yaml.safe_load`. That is the bug PR
#160 fixed, which was closed unmerged on 2026-08-30, so it is live on `main` again. This
entry and the manifest fields beside it were written by hand instead.
