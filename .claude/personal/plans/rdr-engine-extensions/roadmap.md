# Feature layer, multi-tree engines, concept trees, OO integration and TMS — Roadmap

Narrative half of `rdr-engine-extensions`. One of seven plans the oversized
`rdr-refactor` was split into on 2026-08-30; the predecessor's full 3,259-line
roadmap remains in the personal-notes branch's history immediately before that
split commit.

## What is being built

Everything the forward architecture puts on top of the single-class engine. The
design lives in `rdr_architecture_plan.md`, which has never landed — it was
carried by a pull request closed unmerged, and re-landing it is this plan's last
item.

- **Feature layer, the "poor man's Rete"** (`rdr-feature-registry` →
  `rdr-feature-capture`). Named, memoized, registry-backed derived features that
  rules reference by name, with one `CaseView` per case per run — so each
  feature is computed once regardless of how many rules mention it. Then
  knowledge-acquisition-time capture: a `%feature` magic, hash-based
  deduplication of equivalent expressions, and registry autocomplete.
- **Multi-tree engines** (`rdr-multi-class` → `rdr-general-fixpoint`). MCRDR
  first: multi-valued and iterable conclusion attributes, which lifts the
  single-valued guard the underspecified adapter enforces. Then GRDR: the naive
  fixpoint loop, the monotonic-conclusions contract, and recorded dependency
  edges.
- **Concept trees, NRDR** (`rdr-concept-trees`). Trees declared as *vocabulary*
  — named boolean or typed conclusions other trees may reference — with an
  explicit declared dependency graph between trees, stratified evaluation order,
  semi-naive re-firing under Datalog semantics, cornerstone-regression checks
  when a shared concept is edited, and upstream-fix routing in the acquisition
  interface.
- **OO integration** (`rdr-oo-definitions`). Per-class `definition` RDRs
  colocated with the class as a Specification pattern, candidate generators in a
  hypothesize-and-test shape, the case as a `(candidate, scoped view)` pair
  respecting the Law of Demeter, and taxonomy-level discriminators for exclusive
  siblings. The engine supplies upstream conclusions bottom-up over the
  dependency graph between class definitions, so definitions never call
  definitions — inversion of control is the point.
- **TMS justifications** (`rdr-justifications`). A `Justification` value object
  plus a `JustificationRecorder(EvaluationObserver)`, and retraction propagation
  over the dependency graph, giving incremental recompute on world change and
  explanations for free.
- **The architecture brief** (`rdr-architecture-brief`).

## Decisions that still bind

**1. The brief is deliberately last, not an early trivial doc PR.** It was
originally framed as a small independent Wave-0 change. The plan owner's call
was that it reads as a description of a *finished* system, so landing it
mid-refactor is the wrong sequencing. Its `depends_on` names the two integration
tips as a best-guess proxy for "the engine is stable"; revisit the exact edge
when the item is picked up.

**2. The closed brief branch is kept rather than deleted.** Its content was
already refreshed once — the post-split repository mapping table, the
auto-serialization claim, the de-prefixed module names — so re-landing it is a
re-verify against whatever the engine looks like by then, not a rewrite.

**3. The OO prototypes are input to harvest, not branches to merge.**
`rdr-oo-recognition` (#21) carries an `rdr/recognition/` package — definition,
engine, registry, candidate generators, predicates and their tests — and
`rdr-backend-unification` (#22) unifies recognition with the query and
underspecified backend frontend. Both are drafts on bases that were closed
without merging, so their commits are in neither the upstream base nor any open
fork branch. A maintenance pass cannot invent a target for them and reports them
to their owner instead. `rdr-oo-recognition` keeps `deferred` rather than
`blocked`: both are true of it, and the deferral is the developer's own
decision, so the dead base is recorded beside it rather than overwriting it.

**4. Truth unification is a prerequisite of the justifications, and it has
landed.** `eql-truth-unification` (#99) is in the
`eql-core-and-code-generation` plan and has merged, so nothing is waiting on it;
its `depends_on` edge is dropped rather than kept as a cross-plan reference the
schema cannot express.

**5. The multi-tree track has an existing engine to port from, not to invent.**
The current `entity_query_language/rdr` has single-class only; MCRDR and the
general fixpoint loop are ported from the legacy `ripple_down_rules` package,
with the dependency graph and the monotonic-conclusions contract designed in
rather than inherited.

## Cross-plan dependencies, and what they cost

`rdr-feature-registry` and `rdr-multi-class` both stack on `d-core-backend`
(#210) in `rdr-core-engine`. `depends_on` cannot name an item in another plan,
so both edges are recorded as `blockers` and those two items carry no dependency
chip and no automatic readiness computation. Everything downstream of them —
concept trees, and through them OO integration, justifications and the brief —
keeps its edges, since the whole chain lives here.

## Open

- **How this track relates to the explanation track.** The
  EQL-as-formal-derivation versus natural-language-gloss distinction that
  `rdr-explanation`'s audience rendering rests on is the same one the TMS
  justifications produce. Neither has been designed with the other in view yet,
  and they should be.
- **Whether the feature layer and MCRDR can genuinely run in parallel.** They
  are recorded as independent tracks on the same base, but MCRDR lifts a guard
  in `underspecified.py` that the feature layer does not touch, so the claim has
  not been tested against real diffs.
- **Nothing here has a branch.** Every item is `blocked`, `not_started` or
  `deferred`, gated on the core engine's stack landing.

## Standing conventions

- Follow `.claude/personal/cram-notes.md` and this repository's `AGENTS.md`.
- SOLID is a review gate: a new capability enters as an abstraction plus small
  dataclass implementations, and strategies stay substitutable without touching
  the engine.
- TDD: failing test first, and no test is modified to make something pass.
- `krrood` stays self-contained; world-like scenarios are mimicked in
  `test/krrood_test/dataset`.
- Sessions may run in parallel only if their pull requests touch disjoint files
  *and* neither needs the other's branch as a base. Everything below `main` here
  is stacked, so "parallel" means parallel tracks, each internally sequential.
- The programme's working method — run the probe rather than reasoning, compare
  sorted collected test ids rather than counts, stage by explicit path — is
  recorded in `rdr-core-engine`'s roadmap and applies here unchanged.
