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
  PR #87 (draft, base main, subscribed to all activity, all 12 review threads resolved).
  Redesigned after developer review (see PR-progress section above for the full account):
  operand naming and disambiguation now live entirely in `ReferringExpressions`/
  `DistinguisherIndex` (coreference-driven, identity-keyed) instead of a parallel predicate-side
  module — `operand_naming.py` and its heuristics (generic-name list, ordinal stripping,
  occurrence-count anonymity) are deleted. Final precedence (supersedes decision 1's original
  ordering): operand's own type wins when informative → field metadata → field name → "object".
  Same-noun pairs read "a X … another X" (indefinite alternative, not "the other X" on first
  mention); larger groups use ordinals, not numbers. Full suite verified against baseline
  (zero regressions).
- P3 [ ] general, on P2 — value-agnostic + concrete-subclass forms (decision 3). Dep: P2.
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

