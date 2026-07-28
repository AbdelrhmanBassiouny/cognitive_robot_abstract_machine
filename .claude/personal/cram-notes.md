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
- P1 [x] **merged to `main`** (PR #86) — branch `claude/eql-verbalization-p1-surface-verification-eqltzc`,
  off `main`. `surface_verification.py` was itself later moved to
  `krrood.entity_query_language.testing.surface_verification` by further main-branch work (not this
  plan's own session) — P3 picked up that move on its 2026-07-24 rebase, see P3's entry below.
  Extracted `surface_verification.py`
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
- P2 [x] **merged to `main`** (PR #87), general, off `main` — operand-naming architecture
  (decisions 1, 2, 4). Keystone; gated #33 and P3. Also picked up a `Distinguisher` refactor
  (single frozen dataclass → `Distinguisher(ABC)` base with `AlternativeDistinguisher`/
  `OrdinalDistinguisher` subclasses) as part of its continued review before merging — P3's
  2026-07-24 rebase onto `main` picked that up too (no P3-side change needed, non-overlapping
  code). Originally pushed to `claude/eql-verbalization-operand-naming-n0gb95`.
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
  - Renders per decision 3's literal example, *"a Body or a Region"* — each alternative gets its
    own repeated indefinite article. The PR originally shipped a bare-compound-head divergence
    (*"a Body or Region"*, one shared determiner, reusing `NounPhrase` completely unchanged) to
    avoid growing `NounPhrase`; review round 11 pushed back on that divergence and it was
    reverted in favour of decision 3 as written — see that round's entry below for the
    `NounPhrase.additional_heads` mechanism that replaced it.
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
  - Tests: krrood-internal mimics only (`Shape`/`Circle`/`Square`, an `Instrument`/`Drum`/`Flute`/
    `Harp` three-member family, an over-cap `Polygon` family of 7, a concrete `ConcreteBase` with
    subclasses) in `test_operand_referring.py` + new `test_first_order_form.py`.
  - Real end-to-end proof against the actual `Visible`/`Body`/`Region` sdt predicates waits for
    P4 (those predicates aren't migrated to classes yet).
  - **Review round 3** (oxford_comma question, pushed dbc4444f): `operand_head_noun`'s abstract-
    type label used a manual `" or ".join(...)` instead of reusing `disjunctive_type_head`'s
    Oxford-comma joining — a real latent bug (2 alternatives happened to agree, 3+ would've
    silently diverged, e.g. "Drum or Flute or Harp" vs the real "Drum, Flute, or Harp"). Fixed to
    reuse `disjunctive_type_head` directly; the `Instrument` family locks it in. Resolved.
  - **Review round 4** (`first_order_form` overrides question, pushed 19280e06): a truly
    value-agnostic rendering needs nothing external, so `operand_overrides` had no business on
    the general `placeholder_operands`/`first_order_form` signatures — moved into
    `SymbolicSurfaceSnapshot` itself, which layers its own registered overrides on top. Resolved.
  - **Review round 5** (test-quality question, pushed 68cea9fd): the override test asserted the
    overridden and un-overridden renderings were *equal* — proved nothing, since the mimic
    predicate's fragment never read the overridden field. Gave the mimic's fragment a second
    clause reading that field too, so the override's effect became genuinely visible in the
    rendered sentence. Resolved.
  - **2026-07-24 rebase** (base retargeted from P2's branch to `main`, now that #86+#87 merged):
    fetched main (which had ~5 days of substantial unrelated activity — a `code_generation`
    package extraction, `robokudo`/`semantic_digital_twin` work, `surface_verification.py` moved
    to `krrood.entity_query_language.testing.surface_verification`, and P2's own continued
    review round moving `Distinguisher` to an ABC hierarchy and `GrammarMetadata` to
    `krrood.entity_query_language.verbalization.grammar_metadata`). CI had failed with
    `ImportError: cannot import name 'GrammarMetadata'` — fixed the two stale
    `krrood.patterns.field_metadata` imports (`referring.py`, `test_operand_referring.py`) to the
    new module, confirmed the only other CI failure (`test_world_sim_state_sync` in
    `semantic_digital_twin`) is an unrelated pre-existing flaky physics-settling test. Then merged
    `main` into the branch directly (3 conflicts, all mechanical import-only: `referring.py`'s
    import block, a duplicate `GrammarMetadata` import in `test_operand_referring.py`, an unused
    `SymbolicCallable` import in `verbalization_surfaces.py` — verified via a disposable
    `git worktree` trial merge first that nothing deeper conflicted, given `Distinguisher`'s ABC
    refactor lives in the same file) and fixed `test_first_order_form.py`'s import of
    `surface_verification` to the new `testing` package path. `mergeable_state` now `clean`; PR
    base retargeted to `main`; description updated to reflect the now-focused diff (7 files,
    +733/-72, no more phantom P1/P2 content). Full `test/krrood_test/` suite green (2012 passed, 9
    skipped) apart from two pre-existing unrelated failures (`graphviz`/`dot` missing in this
    sandbox). black + docformatter applied throughout.
  - **Review round 6** (2026-07-25, reconciliation question): asked whether the branch was still
    reconciled with `main` and the `VerbalizationSurface` changes. Checked `git log` for commits on
    `main` since the 2026-07-24 rebase touching `krrood/entity_query_language/verbalization/` or
    `krrood/entity_query_language/testing/` — none (the ~78 newer commits are all unrelated
    `semantic_digital_twin`/`ripple_down_rules`/mujoco/robocasa work). Replied confirming, not
    resolved (informational, matches past practice for this kind of question).
  - **Review round 7** (`_concrete_type_alternatives`/`operand_type_alternatives` returning
    `Optional[Tuple[...]]`, 2 comments): "why not just return an empty tuple?" — both functions,
    `NounForm.type_alternatives`, and `ReferringExpressions.type_alternatives_of` now use `()`
    throughout instead of `None`/`Optional`; `_HeadNounGrouping.add`'s `type_alternatives` param
    defaults to `()` too. Both threads reply-and-resolved.
  - **Review round 8** (`disjunctive_type_head`'s manual `oxford_comma`/`Conjunctions.OR` call):
    "isn't there a `DisjunctivePhrase` in parts of speech that does exactly this?" — yes; swapped
    the manual join for `DisjunctivePhrase(alternatives).as_fragment()`. Resolved (though this
    function's role narrowed further in round 11 — see below).
  - **Review round 9** ("cannonical" ambiguous, 2 comments): renamed every "canonical"-family
    identifier in `referring.py` to "representative" — `canonical_of`→`representative_of`,
    `noun_of_canonical`→`noun_of_representative`, `canonicals_by_noun`→`representatives_by_noun`,
    `members_by_canonical`→`members_by_representative`, `_noun_of_canonical`→
    `_noun_of_representative`, `_type_alternatives_of_canonical`→
    `_type_alternatives_of_representative`, plus local variables and docstrings. Verified a
    case-insensitive grep for "canonical" across the file afterward returns zero matches. Both
    threads reply-and-resolved.
  - **Review round 10** ("make all these classes as dataclasses", `test_operand_referring.py`):
    `@dataclass`-decorated every mimic class lacking it — `Shape`/`Circle`/`Square`,
    `Instrument`/`Drum`/`Flute`/`Harp`, `Polygon` and its seven concrete subclasses, `ConcreteBase`/
    `ConcreteBaseVariant`, `Sensor` — plus the equivalent classes in `test_first_order_form.py`
    (`Igniter`, `Fastener`/`Bolt`/`Screw`) for consistency, since the same rule applies there too
    though not explicitly flagged. Resolved.
  - **Review round 11** (the repeated-article pushback — "shouldn't there be an `a` before
    square?"): the shipped divergence (one shared article, *"a Body or Region"*) was wrong; the
    developer wanted decision 3's original *"a Body or a Region"*. A naive fix (bake a second
    article into the disjunctive text, leave the outer phrase's determiner bare) would have been
    wrong on repeat/definite mention (*"the Circle or a Square"*, mixed definiteness). Instead
    `NounPhrase` gained `additional_heads: List[VerbalizationFragment]` — further disjunctive
    heads sharing the phrase's definiteness/number/alternative/ordinal, each choosing its own
    article independently. `DeterminerProcessor._lower_noun_phrase` now builds one
    determiner-and-head group per head (factored into a new `_head_group` helper) and joins them
    with "or" (Oxford-comma style at 3+, via the existing `oxford_comma`); falls back to exactly
    the old single-head behaviour when `additional_heads` is empty, so the ~10 other `NounPhrase`
    call sites are unaffected. `VariableRule.build` now constructs the `NounPhrase` directly from
    `NounForm.type_alternatives` (first alternative as `head`, rest as `additional_heads`) instead
    of going through `disjunctive_type_head`, which is now solely `operand_head_noun`'s internal
    same-noun grouping-key text generator (its own docstring, and `NounForm.type_alternatives`'s,
    updated to say so explicitly). Updated the affected end-to-end sentences (*"a Circle or a
    Square is warm"*, *"a Drum, a Flute, or a Harp is warm"*, `first_order_form`'s *"a Bolt or a
    Screw is secure"*). Full `test_verbalization/` suite green (756/3 skipped); full
    `test/krrood_test/` suite unchanged from the 2026-07-24 baseline (2012 passed, same 2
    pre-existing unrelated `graphviz` failures). Pushed as commit 33a8da5b; PR description
    rewritten to describe the repeated-article design instead of the old shared-article
    trade-off. Resolved.
  - **Review round 12** (2026-07-26, 4 comments): (a) `NounPhrase.additional_heads` design
    question — "why must they be distinct alternatives, why a separate attribute, discuss with
    me." Replied with reasoning rather than a code change: distinctness isn't required or checked
    (a caller could pass duplicates, they'd just render pointlessly, e.g. "a Body or a Body");
    considered unifying `head`+`additional_heads` into one `heads: Tuple[...]` but rejected it —
    `head` is structurally special (ordinal/pre_head attach only there, it's the phonology anchor
    for the ordinary non-disjunctive case), so merging would hide that asymmetry behind an
    implicit "index 0 is special" rule instead of stating it in the type, and would touch ~20
    unrelated `NounPhrase(head=...)` call sites for no benefit. Recommended keeping the shipped
    shape; **left unresolved**, awaiting the developer's response (explicit "discuss with me").
    (b) "Isn't this more grammatically correct than a single article? Discuss with me" (defending
    the repeated-article choice) — replied with the concrete argument: a shared article is
    provably wrong the moment two alternatives need different articles (e.g. `Apple`/`Banana` —
    no single "a"/"an" works for both), which `_concrete_type_alternatives` can't rule out since it
    accepts any abstract base's subclass names; repeated article is immune by construction. Cited
    Fowler's/CGEL as secondary style support. **Left unresolved** (explicit discuss request).
    (c) "Is it fine that referring.py imports from parts_of_speech? Shared low-level impl instead?"
    — a real layering violation: `parts_of_speech.py` (vocabulary) already imports from
    `microplanning.coordination`/`possessive`, so `referring.py` (microplanning) importing back
    from `parts_of_speech` crossed the boundary both ways. Fixed: added `disjunctive_phrase()` to
    `microplanning.coordination` (next to the near-identical existing `one_of()`); both
    `DisjunctivePhrase.as_fragment` and `disjunctive_type_head` now call it, and `referring.py`'s
    import of `vocabulary.parts_of_speech` is gone entirely. Resolved. (d) "Representative what?
    Same problem as canonical, needs a complementary word" — round 9's rename fixed the ambiguous
    word but left "representative" bare as a noun in several docstrings; standardized on
    "representative referent" throughout the file (every field docstring in `DistinguisherIndex`/
    `_HeadNounGrouping`, `distinguisher_for`, `add`, `head_nouns`, `type_alternatives`,
    `_group_referents_by_noun`, `referent_aliases`). Resolved. Pushed as commit a4a69b06; full
    `test_verbalization/` suite green (756/3 skipped), full `test/krrood_test/` suite unchanged
    (2012 passed, same 2 pre-existing `graphviz` failures).
  - **Review round 13** (2026-07-26, 3 comments, same day as round 12): (a) the grammar-
    justification thread (round 12b) got no further reply from the developer — they resolved it
    themselves after reading the Apple/Banana argument, no action needed. (b) follow-up on the
    `additional_heads` design thread (round 12a): "Ok keep it, however I'd like to see how this
    behaves — e.g. re-mentioning the variable elsewhere in the query." Built exactly that
    scenario (`and_(AbstractOperandRole(shape), VisibleFromSensor(shape, sensor))` — a second,
    non-pronoun mention) and it exposed a real bug: `CoreferenceProcessor._reduced()` (the
    definite-repeat-mention path) rebuilt `NounPhrase` from scratch naming only
    head/number/definiteness/referent_id/alternative/ordinal — `additional_heads` was never
    listed, so a repeat mention silently dropped every alternative but the first ("the Circle"
    instead of "the Circle or the Square"). `_rebuilt()` had a milder version (preserved via
    `replace()` but never walked). Fixed both to propagate + walk `additional_heads` exactly like
    `head`; added a permanent regression test
    (`test_reused_abstract_operand_reads_as_a_definite_disjunction_on_repeat_mention`). Resolved.
    (c) "Don't mention users/callers in a docstring, it goes stale — add this to AGENTS.md" (on
    `disjunctive_phrase`'s docstring, which had named `DisjunctivePhrase`/`disjunctive_type_head`
    as its "the shared building block behind" callers) — reworded to describe behavior/contract
    only; added the rule to `AGENTS.md`'s Documentation section. Resolved. Also fixed, unprompted
    but same underlying issue: an awkward doubled "representative referent *representative*"
    docstring phrase from round 12's rename pass (developer flagged it directly) — reworded.
    Pushed as commit e66bf4b5; full `test_verbalization/` suite green (757/3 skipped, +1 for the
    new regression test), full `test/krrood_test/` suite green (2013 passed, same 2 pre-existing
    unrelated `graphviz` failures).
  - **Review round 14** (2026-07-26, 3 comments, same day as round 13): (a) round 13's `add`
    docstring fix ("the representative referent *representative* names") was itself flagged
    "again awkward wording" — simplified further by dropping the attempt to redefine
    "representative" inline entirely; the method now just says "Record *referent_id* as a member
    of *representative*, registering it under *noun* …", relying on the class's own field
    docstrings to already establish what a representative referent is. Resolved. (b) "Will these
    ever pronominalise to 'it'? Maybe in a full query? Add tests" (on the repeat-mention
    regression test from round 13) — yes; added
    `test_reused_abstract_operand_pronominalises_on_every_mention_within_its_scope`, the pronoun
    companion to round 13's definite-repeat test: a disjunctively-typed variable as a full
    entity-query subject pronominalises to "it" on *every* mention inside that WHERE scope (not
    just the first repeat), while the one spelled-out first mention keeps the full disjunction —
    together the two tests cover both branches `CoreferenceProcessor` can take on a repeat
    mention of a disjunctive head. Resolved. (c) "Point AGENTS.md's docformatter rule at the
    actual repo script instead" — changed "Always run `docformatter`..." to "Always run
    `scripts/format_docstrings.py` (black + docformatter)...", matching what every P1–P4 session
    actually runs. Resolved. Pushed as commit ea595142; full `test_verbalization/` suite green
    (758/3 skipped, +1 for the new pronoun test), full `test/krrood_test/` suite green (2014
    passed, same 2 pre-existing unrelated `graphviz` failures). Also noted: CI on this same head
    SHA showed a `coraplex` job failure (an `ormatic_interface.py` regeneration/`ruff format`
    internal error) and the recurring pre-existing `semantic_digital_twin` flake
    (`test_world_sim_state_sync`) — both confirmed unrelated to this PR (neither touches any file
    this PR changes; the `coraplex` one is an ORM-generation issue this session correctly left
    alone per AGENTS.md's guidance never to hand-fix `ormatic_interface.py`). `krrood`'s own job
    passed.
  - **Unexpected merge on the branch** (2026-07-27, discovered mid-round-15): pushing round 15's
    commit hit a non-fast-forward rejection — `origin/claude/eql-verbalization-p3-albw76` had
    moved to a merge commit (`6b51075e`, "Merge remote-tracking branch 'origin/main'") authored
    as `Claude <noreply@anthropic.com>` — **not by this session**, and in direct violation of
    AGENTS.md's Version Control rule (commits must be the human identity, never an assistant
    identity/`noreply@anthropic.com`). Investigated before doing anything: diffed my last commit
    against that merge commit's tree for the one file it touched that overlaps this PR
    (`test_operand_referring.py`) and confirmed every P3 class/test survived intact — the only
    real change was a one-line `FieldMetadata(other_metadata=[...])` → `GrammarMetadata(...)`
    update reflecting an unrelated main-branch API simplification. Did **not** attempt to rewrite
    or force-push to fix the bad authorship (that would rewrite already-pushed shared history
    unilaterally, which AGENTS.md and this session's own conventions rule out without explicit
    permission) — instead did a plain `git rebase origin/<branch>` (safe: only replays this
    session's own not-yet-pushed commit, touches nothing already on the remote), fixed one
    resulting unused `FieldMetadata` import the merge's API change left behind, verified the full
    suite, and pushed normally (fast-forward, no force). Flagged the authorship-policy violation
    to the user for their awareness; not something to silently ignore, but also not something to
    unilaterally "fix" via history rewrite.
  - **Review round 15** (2026-07-27, 3 comments): (a) "docstrings read like a conversation, talk
    about hypothetical bad designs instead of being short/to the point, no comparison, no
    historical context — make this a rule in AGENTS.md and apply everywhere; also don't scream
    words in all caps, check and fix everywhere; apply the formatting script to all modified
    files." Added both rules to AGENTS.md's Documentation section. Trimmed every narrative/
    comparison docstring this PR's `additional_heads` work had introduced (`NounPhrase.
    additional_heads`, `disjunctive_type_head`, `NounForm.type_alternatives`, `DeterminerProcessor.
    _head_group`, `CoreferenceProcessor._reduced`) down to plain statements of behavior. Fixed the
    three leftover ALL-CAPS "VALUE" instances in `surface_verification.py` (pre-existing from P1,
    not this round's own writing, but part of this PR's diff) to RST `*value*`. Ran
    `scripts/format_docstrings.py` on every touched file. Resolved. (b) "`first_order_form`/
    `placeholder_operands` missing a doctest example, and it needs to be added to the auto-tested
    doctests" — added `>>> first_order_form(IsReachable)` / `placeholder_operands(IsReachable)`
    examples (reusing the same shared example-domain predicate every other doctest in the codebase
    already uses); discovered `surface_verification.py` lives in `krrood.entity_query_language.
    testing`, outside the `verbalization` package `test_rule_doctests.py` auto-discovers by
    walking, so the new doctest would have silently never run — extended that harness to also
    walk the `testing` package and added a regression test locking in the new coverage. Resolved.
    (c) "add and check parameter docstrings everywhere" (on `determiner_processor.py`) —
    `_head_group` had zero `:param:` entries for its 4 parameters and `_lower_noun_phrase` had a
    `:return:` but no `:param:`; added both. Resolved. Pushed as commit 91e3ca4b (on top of the
    unexpected merge, reconciled as above); full `test_verbalization/` suite green (760/3
    skipped), full `test/krrood_test/` suite green (2012 passed — count shifted from the
    unrelated main-merge's own test changes, not this PR — same 2 pre-existing `graphviz`
    failures). PR was ready-for-review (developer's own action from round 14's check-in); per
    personal convention, converted back to draft after this round's push.
  - **Type-verbalization scatter audit** (2026-07-28, direct chat question, not a GitHub review
    comment): developer asked whether Type-verbalization logic is spread across too many places
    and to discuss before fixing. Dispatched a research subagent to map every call site under
    `verbalization/` that renders a Python `type`. Finding: mostly a clean layered pipeline
    (`type_noun` → `RoleFragment.for_type`/`for_value` → `disjunctive_phrase`/`one_of` →
    `referring.py`'s abstract→concrete expansion → `OneOf`/`DisjunctivePhrase` → `HasType`/
    `HasTypes`) — most cross-file references are legitimate reuse, not duplication. Three
    exceptions found and discussed: (1) "is this a homogeneous tuple/list of classes" reimplemented
    3x (`value_lexicon.value_phrase`, `LiteralRule._type_members`, `OneOf`'s `are_types`); (2)
    `value_phrase`'s tuple-of-types branch is dead code (shadowed by `LiteralRule`'s own tuple
    handling) *and* contradicts it (joins with "or", unlinked, vs. `LiteralRule`'s "and", linked);
    (3) "class name with a fallback" written 3x (`type_noun`, `FallbackNouns.name_of`,
    `InstantiatedPlanner._type_name`), neither of the latter two delegating to `type_noun`. User
    approved fixing all three. Fixed (1)+(2): extracted `type_members()` to `value_lexicon.py`,
    pointed `LiteralRule`/`OneOf` at it, deleted `value_phrase`'s dead/contradictory branch.
    **Did NOT fix (3)** after empirically testing it first: routing `FallbackNouns.name_of`
    through `type_noun` broke `test_limit_verbalization.py` — a bare-`int`-typed query subject is
    *regression-tested* to read "the top three ints" (raw lowercase `__name__`), a deliberately
    different grammatical role from `type_noun`'s "Integer" value/literal convention, not an
    accidental duplicate; reverted that one change. Also left `InstantiatedPlanner._type_name`
    alone — its `_type_` is typed `Union[Type[T], Callable]`, broader than `type_noun` safely
    handles (a `functools.partial`-like callable lacking `__name__` would crash it), so unifying
    would be a regression risk for a case that isn't really "the same thing" after all. Pushed as
    commit 99ea09ee; full `test_verbalization/` suite green (760/3 skipped), full
    `test/krrood_test/` suite green (2012 passed, same 2 pre-existing `graphviz` failures).
    `mergeable_state` now reports `clean`.
  - **Follow-up correction** (2026-07-28, same day): developer overrode the (3) decision above —
    "the limit verbalization should [read] the top three Integers", i.e. the `int`-as-query-subject
    wording that `test_limit_verbalization.py` had locked in ("the top three ints") was itself the
    stray inconsistency, not a deliberate convention; the fix should go through after all.
    Re-applied `FallbackNouns.name_of` → `type_noun`, and updated all 6 affected assertions in
    `test_limit_verbalization.py` to the "Integer"/"Integers" wording (a legitimate spec
    correction from the developer, not test-cheating — AGENTS.md's "never modify the test when
    fixing a failing test" is about not papering over a bug, not about refusing an explicit
    behavior-change instruction from the person who owns the intended output). Verified this was
    the *only* test file affected by grepping the full suite run. Pushed as commit c1e95cbe; full
    `test_verbalization/` suite green (760/3 skipped), full `test/krrood_test/` suite green (2012
    passed, same 2 pre-existing `graphviz` failures).
  - **Review round 16** (2026-07-28, 1 comment): "This should be any iterable, not just list and
    tuple" (on `type_members`, `value_lexicon.py`, added by round-`99ea09ee`'s consolidation) —
    broadened the guard to `isinstance(value, (str, bytes)) or not isinstance(value, Iterable)`,
    matching `DisjunctivePhrase.as_fragment`'s existing "any iterable, not str/bytes" convention;
    added a `set`-based doctest (`sorted(...)`-wrapped for determinism). `LiteralRule`/`OneOf` call
    sites unaffected (contract unchanged). Pushed as commit d45003c7; full `test_verbalization/`
    suite green (760/3 skipped), full `test/krrood_test/` suite green (2012 passed, same 2
    pre-existing `graphviz` failures). Reply-and-resolved.
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

