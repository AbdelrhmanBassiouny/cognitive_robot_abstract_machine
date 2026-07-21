# Personal Claude Code notes (abdelrhmanbassiouny only)

These are personal workflow preferences for working on this fork, not project
conventions. They live on the `claude/personal-notes` branch only and are pulled
into every session by the `.claude/hooks/session-start.sh` hook (see the
`claude/session-hooks` branch); this file itself must never be merged into `main`.

## Pull requests

- Always open pull requests as **drafts**. Never open a PR as ready-for-review
  by default; mark it ready only when explicitly told to.
- Always convert a PR back to **draft** after pushing any commit to it or
  otherwise modifying it, even if it was previously marked ready for review.
  Mark it ready again only when explicitly told to.
- Bug-fix PRs must always carry the **`bug`** label.
- Keep bug-fix PRs focused: one root cause per PR, based off `main`, no
  unrelated cleanup bundled in.
- Always include a link to the session that created the PR in the PR
  description.
- Keep the PR description up to date: after pushing any change that alters
  what the PR does, update the description to match. Never leave it
  describing an earlier state of the PR.
- Always subscribe to all events on every PR you open - including plain
  conversation comments, not just inline review comments - and handle each
  event with an explanation summary in the session chat.

## Review comments

- Resolve a review comment thread only once you have genuinely done what it
  asked. If instead you need to ask what to do, or you are not taking an
  action, do not resolve it — reply explaining the situation and asking the
  question.
- Always reply to a PR comment explaining what you did before resolving it.

## Before starting work

- Always fetch, pull, and merge from the original repository you cloned (the
  user-owned repository, whether it is a fork of another or not) before
  investigating problems, reacting to events, or implementing features, so
  you are always working from its latest state.

## PR plan and progress tracking

- For every PR you create, maintain a plan/progress/next-steps note in
  CLAUDE.local.md's PR-progress section (the block between the
  BEGIN-PR-PROGRESS/END-PR-PROGRESS markers, written automatically by
  session-start.sh). Initialize it with a short plan as soon as you start
  real work on the PR.
- Keep it current: update it whenever the plan changes, whenever you update
  your task list, and before ending any turn that changed either. Run
  `save-pr-progress.sh` whenever you update it.
- Never write this plan into any file tracked on the PR branch itself. It
  must live only in the PR-progress section, which is stored on the
  `claude/personal-notes` branch and is never merged.

## Plan-mode approval → persistent plans

- The moment a normal Claude Code plan-mode plan is approved, before implementing, judge whether
  the work spans multiple PRs/branches/sessions to complete. If it's contained in one PR from this
  session, just implement it - do not invoke anything below for it.
- If it spans multiple PRs/sessions:
  - **No existing plan covers it**: invoke `/plan-create <plan-id>`, handing it the just-approved
    plan-mode markdown directly as source material - it's valid input under that skill's "existing
    freeform doc to migrate" case even though it only lives in this conversation, not a file.
  - **An existing plan covers/extends it** (check auto-discovery on the current branch, or ask):
    if this session is that plan's designated planning/steward session, edit `plan.yaml` directly
    and run `save-plan.sh` + `/plan-dashboard <plan-id>`; otherwise comment-propose it on the
    plan's `tracking_issue` instead of editing directly - see
    `.claude/personal/plans/README.md`'s "Proposing structural changes" section.
- This is the moment that decides whether the plan gets captured durably or evaporates once the
  session ends - do not let it pass by default.

<!--
Add new personal-only rules below this line. Keep each rule short and
imperative, same style as above.
-->

## EQL verbalization follow-up plan (PR #33 review) — living roadmap

Cross-PR roadmap for the semantic_digital_twin verbalization review on PR #33. Every
session working P1–P4 below: READ this section first, keep its status current (check off
items, record decisions and any agreed divergence), and run `save-personal-notes.sh` when
it changes. #32 (SymbolicFunction migration) is merged to `main`.

### Finalized design decisions
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
9. ormatic `type`-mappability PR: DROPPED (maintainer). `OPERAND_OVERRIDES` stays; its
   only cleanup is the `SymbolicCallableOverride` dataclass in P1.
10. Keep surfaces concise (omit root/tip from `BlockingBodies`); details are query-able.

### Every P1–P4 session must
- Critically evaluate first: don't blindly implement; assess vs this codebase's
  verbalization/EQL architecture, the literature (NLG surface realization, grammar
  frameworks, snapshot testing), and reliability/scalability/maintainability + SOLID.
  Surface a better approach or a flaw and discuss before implementing.
- Follow AGENTS.md incl. Version Control (commit as the human identity, no assistant
  trailers, "Made with the help of Claude." note allowed), no abbreviations, dataclasses,
  absolute/top-level imports, RST field docstrings, no `getattr`, guard clauses, SOLID,
  TDD, black+docformatter (`scripts/format_docstrings.py`).
- The exhaustive `SymbolicSurfaceSnapshot` test is the coverage mechanism; keep it green.
- To render sdt/coraplex surfaces locally: build random_events (`pip install ./random_events`
  → gives native `random_events_lib.reals`), `pip install trimesh mujoco daqp plyfile lxml`,
  PYTHONPATH = krrood/src + <pkg>/src + giskardpy/src + probabilistic_model/src +
  coraplex/src + repo root, and stub `giskardpy_bullet_bindings` (MagicMock in sys.modules)
  before importing — rendering needs type names, not physics. CI has the real stack; commit
  no env hacks.

### The four PRs  ( [ ] todo / [~] in progress / [x] done )
- P1 [x] done — branch `claude/eql-verbalization-p1-surface-verification-eqltzc`, off `main`,
  PR #86 (draft, subscribed to all activity). Extracted `surface_verification.py`
  (`VerbalizationSurface`, `SymbolicCallableOverride`, `SymbolicSurfaceSnapshot`) and rewired
  krrood's surface test/snapshot onto it; general `class_implements_own_method` added to
  `class_diagrams/utils.py`, unit-tested. Review round (5 comments) addressed and pushed
  (92d4a9b3): (a) `class_implements_own_method` redesigned per developer feedback to take two
  already-resolved methods (`Subclass.method_name`, `BaseClass.method_name`) instead of
  `(cls, base_class, method_name)` — caller does ordinary attribute access, no more
  `inspect.getattr_static`, no string-typed lookup; (b) `phrase_rule._is_guarded` reverted to
  the plain `type(rule).when is not PhraseRule.when` comparison — `when` is a plain instance
  method, never classmethod/staticmethod, so the direct comparison was already correct and the
  util added needless indirection there; (c) explained (no code change, thread resolved) why
  `assert_every_callable_has_a_fragment` isn't redundant with Python's own abstractmethod
  enforcement — `assert_surfaces_cover_every_callable` explicitly filters fragment-less classes
  out via `if self.has_fragment(cls)`, so only this assertion catches a fragment-less predicate,
  and it does so immediately rather than lazily at some future instantiation site.
  Review round 2, developer answered both open threads, pushed (26984976): (d)
  `SymbolicCallableOverride` (a class wrapping `Dict[str, Any]`) replaced with
  `OverriddenOperand(name: str, value: Any)` — one dataclass per overridden field, so
  `operand_overrides` is now `Dict[Type[SymbolicCallable], Sequence[OverriddenOperand]]`
  (developer's answer kept `Any`, just wanted the per-field-entry shape, not the type-narrowed
  one I'd pushed back on); (e) `class_implements_own_method`'s params retyped `Callable` instead
  of `Any` per a follow-up comment (mind the gap: I initially mis-replied to the wrong/old
  resolved thread before catching it and reposting on the right one — check thread targets
  carefully when several land in one batch); (f) added the "why not redundant with
  abstractmethod" reasoning into `assert_every_callable_has_a_fragment`'s docstring per request.
  Last thread (whether the three separate `assert_*`-per-test functions should collapse into
  `SNAPSHOT.test()`) resolved by the developer directly with no further comment — implicit
  acceptance of keeping them separate as argued (per-property pass/fail granularity). All 6
  review threads resolved; PR marked ready for review by the developer; description updated to
  match the final diff; CI green (18/18) on 26984976, `mergeable_state: clean`. No formal GitHub
  "Approve" review yet, not acted on unprompted. Verified locally on py3.12 after each round:
  krrood surface test 3/3, util test 7/7, `test_verbalization/` green bar 2 pre-existing
  `jpt`-import env failures (unrelated, present on `main` too). Must merge before #33 rebases.
  No deps.
- P2 [x] general, off `main` — operand-naming architecture (decisions 1, 2, 4). Keystone;
  gates #33 and P3. No deps. DONE & pushed to `claude/eql-verbalization-operand-naming-n0gb95`.
  PR #87 (currently draft — see below, base main, subscribed to all activity).
  Redesigned after developer review (see PR-progress section above for the full account):
  operand naming and disambiguation now live entirely in `ReferringExpressions`/
  `DistinguisherIndex` (coreference-driven, identity-keyed) instead of a parallel predicate-side
  module — `operand_naming.py` and its heuristics (generic-name list, ordinal stripping,
  occurrence-count anonymity) are deleted. Final precedence (supersedes decision 1's original
  ordering): operand's own type wins when informative → field metadata → field name → "object".
  Same-noun pairs read "a X … another X" (indefinite alternative, not "the other X" on first
  mention); larger groups use ordinals, not numbers. Full suite verified against baseline
  (zero regressions).
  Fourth review round (2026-07-20, 4 threads) handled in a follow-up session dispatched as
  branch `claude/pr-87-review-feedback-22080p` — that designated branch turned out to be a
  fresh, unrelated branch off `main` rather than PR #87's actual head, so (per the developer's
  explicit confirmation via AskUserQuestion) the fixes were made directly on
  `claude/eql-verbalization-operand-naming-n0gb95` instead and pushed there (commit b938e46c),
  since that is the only branch that actually updates PR #87. All 4 threads addressed and
  resolved: removed `_OPERAND_DISPLAY_NAME_OBJECT` and its per-field
  `GrammarMetadata(display_name="object")` declarations on `IsClass.obj`, `RuntimeType.obj`,
  `HasType.variable`, `Is.first_entity`/`second_entity`, `IsSameSemanticEntity.entity_1`/
  `entity_2` (`predicate.py`, `factories.py`, `role_predicates.py`) — `operand_head_noun` now
  infers `"object"` straight from a field's `Any` annotation (via the raw dataclass field type,
  not `typing.get_type_hints`, to avoid evaluating unrelated `TYPE_CHECKING`-only forward refs
  elsewhere on the class), so no metadata is needed for those generically-named fields; a field
  genuinely typed `object` (e.g. `IsReachable.location`) is untouched and still falls back to
  its own field name. Also replaced the plain-prose "(Dale & Reiter's Incremental Algorithm...)"
  mention in `operand_head_noun`'s docstring with a proper `:cite:t:`dale1995gricean`` citation
  (that bib entry already existed and is used the same way elsewhere in the file). Verified:
  full `test_verbalization/` suite (710 passed/3 skipped, same pre-existing skips as before) +
  the doctest harness (70/70) + every other krrood_test suite referencing the touched predicate
  classes (`test_match.py`, `test_rendering.py`, `test_core/test_queries.py`,
  `test_core/test_rules.py`, `test_patterns/test_role.py` — 150 passed) green in a fresh
  Python-3.12 venv (root venv was 3.11, which silently breaks `make_dataclass(module=...)` in
  `class_diagram.py` — needed `/usr/bin/python3.12` explicitly). All 4 review threads
  reply-and-resolved; PR converted back to draft after the push per personal convention (it had
  been marked ready for review by the developer at the 2026-07-19 checkpoint).
  Immediate re-review (same day, commit b938e46c → 3 more threads): developer pushed back on the
  Any-type-hint inference itself — wanted `get_type_hints_of_object` (the forward-ref-safe utility
  in `class_diagrams/utils.py`) instead of the raw-annotation-string compare, and for the Any/object
  case to fall back to the plain field name rather than hardcoding `"object"` ("don't skip it and
  don't just name it object"), plus shorter docstrings. Net effect: fully reverted
  `operand_head_noun` to its pre-b938e46c logic (deleted `_field_declares_no_type` outright — once
  the outcome is unconditionally "fall back to field name," the type check has no behavioral role
  left, so `get_type_hints_of_object` ends up unneeded rather than swapped in) and shortened the
  docstring substantially. Separately, two of the reviewer's three comments were "no abbreviations,
  `object`" on `IsClass.obj`/`RuntimeType.obj` specifically — renamed both fields to `object`
  (`self.obj`→`self.object`, `fields["obj"]`→`fields["object"]`), which alone gives them a readable
  surface through the ordinary field-name fallback. Deliberately did *not* rename
  `HasType.variable`/`Is.first_entity`/`second_entity`/`IsSameSemanticEntity.entity_1`/`entity_2` —
  those aren't abbreviations and weren't flagged; updated `verbalization_surfaces.py`'s snapshot to
  their new field-name-based text instead (*"a variable is of type Integer"*, *"a first entity is
  the same object as a second entity"*, *"an entity 1 is the same entity as an entity 2"*) and
  flagged in the reply that a reword is available if wanted. Pushed as commit 3dfa895b; full
  krrood EQL + patterns suite green (1159 passed/3 skipped) after fixing the one surface-snapshot
  regression the revert caused. All 3 threads reply-and-resolved; PR description updated to match
  (the surfaces table and the five-predicates bullet were stale); PR stayed in draft (already was).
- P3 [x] general, on P2 — value-agnostic + concrete-subclass forms (decision 3). DONE & pushed
  to `claude/eql-verbalization-p3-albw76`, PR #88 (draft, base `claude/eql-verbalization-operand-naming-n0gb95`,
  subscribed to all activity). Branch merges in P1 (#86) too: P1 had already extracted exactly
  the first-order-rendering mechanism this phase needed
  (`SymbolicSurfaceSnapshot.placeholder_operands`/`rendered_surface`) into production code, so
  building on it directly avoided a duplicate parallel mechanism — confirmed with the developer
  (AskUserQuestion) before merging P1 in, since the written plan only listed "Dep: P2". PR #88's
  diff therefore also carries P1's + P2's commits (only the last commit is new); noted explicitly
  in the PR description so review isn't confused about authorship.
  - Abstract→concrete-subclass expansion lives in `operand_head_noun` (`referring.py`): triggers
    on `inspect.isabstract(type_)` (not "has subclasses" — a concrete base with subclasses of its
    own, e.g. `SemanticAnnotation`, is still named directly), bounded by the existing
    `MAX_SET_MEMBERS` cap reused from `coordination.py` (a family above the cap falls back to
    naming the abstract type directly, confirmed with the developer). Confirmed with the
    developer (AskUserQuestion) rather than assumed.
  - Divergence from decision 3's literal example: renders as *"a Body or Region"* (one shared
    determiner over a bare disjunctive compound head) rather than *"a Body or a Region"*
    (repeated article per alternative). Getting the repeated-article form would require growing
    `NounPhrase` to support multiple independently-determined heads instead of one; the bare
    compound reuses `NounPhrase`'s existing determiner/coreference/pronoun machinery completely
    unchanged. Flagged explicitly in the PR description as a trade-off, not silently decided —
    open to revisiting if a repeated article is wanted after all.
  - `operand_head_noun`/`NounForm`/`ReferringExpressions` (previously `str`-only) now also thread
    `Tuple[type, ...]` alternatives alongside the plain noun text; `VariableRule.build`
    (`rules.py`) is the single chokepoint that builds the compound fragment (each alternative
    individually source-linked via `RoleFragment.for_type`). `_plural` intentionally left
    untouched (pluralizing a disjunctive head is unhandled, falls back to the plain joined-text
    string with no individual links — an accepted, documented limitation; real population-count
    aggregation over an abstract-typed variable is a rare edge case).
  - First-order (value-agnostic) form promoted to production: `placeholder_operands`/
    `first_order_form` extracted as standalone functions in `surface_verification.py`;
    `SymbolicSurfaceSnapshot` now delegates to them instead of owning the logic. Value-using form
    is simply the existing `verbalize_expression` path over a bound expression — both share the
    same operand-naming resolution, proven by a test that asserts they agree when operand types
    match.
  - Tests: krrood-internal mimics only (`Shape`/`Circle`/`Square`, an over-cap `Polygon` family of
    7, a concrete `ConcreteBase` with subclasses) in `test_operand_referring.py` +
    new `test_first_order_form.py`. Full `test_eql/` + `test_class_diagram/` suite green (1112
    passed, 3 skipped) apart from one pre-existing missing-`mypy` collection error, unrelated.
    black + docformatter applied. CI just kicked off on PR #88 at last check.
  - Real end-to-end proof against the actual `Visible`/`Body`/`Region` sdt predicates waits for
    P4 (those predicates aren't migrated to classes yet).
- P4 [ ] sdt = PR #33, rebased on `main` after P1–P3 — drop the upstreamed framework; apply
  all sdt wording + code-quality items (checklist below). Deps: P1, P2, P3.

### P4 sdt checklist (reasoning/predicates.py, queries.py, robot_predicates.py; test snapshot)
- Reachable: remove `fields["tip"].name`; reword ("a Pose is reachable …"); Pose hint (dec 6).
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
- Regenerate the sdt snapshot; reply-and-resolve each review thread.

