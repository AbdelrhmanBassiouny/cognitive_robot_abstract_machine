# Capability-guarded experts — Roadmap

Narrative half of `rdr-expert-framework`. One of seven plans the oversized
`rdr-refactor` was split into on 2026-08-30; the predecessor's full 3,259-line
roadmap remains in the personal-notes branch's history immediately before that
split commit.

## What is being built

Today the engine decides whether to delegate to an expert by that expert's
*type*. This track promotes an expert's applicability to a first-class,
evaluable EQL **capability guard**, so the engine gates delegation on the guard
instead — which is both the interface-segregation and the Liskov-substitution
fix for the same code.

- **`expert-capability-guards`** — the guard itself, and the retirement of
  `resolution_mode`. The seed already exists: the automatic condition resolver
  becomes one such expert, whose guard is exactly its `_try_auto_resolve`
  eligibility clauses. Those clauses were kept and minimally tidied in the core
  engine's stack specifically so this item has something concrete to generalize
  rather than a blank page.
- **`expert-ensembles`** — cooperating experts, with the existing Hint mode
  re-expressed as composition rather than as a mode, and multi-expert
  arbitration.
- **`expert-capability-verbalization`** — *why can* and *why cannot* this expert
  handle this situation, reusing the rule-tree explanation machinery rather than
  building a second one.

## Why this is its own plan

The idea came out of the `D-core-engine` review on 2026-07-23, which surfaced
three larger designs the split slices could not absorb; this is one of them, and
the review deliberately made it a new wave rather than widening a slice. It sits
between the core engine and the explanation track — it needs the condition
resolver from one and the explanation machinery from the other — which is
exactly why it belongs to neither.

## Decisions that still bind

**1. The guard is an evaluable EQL expression, not a predicate method.** That is
what makes it inspectable, which is what makes the third item possible at all: a
guard you can only *call* can answer "no", but cannot say why. The engine reads
the guard; it does not ask the expert whether it wants the question.

**2. `resolution_mode` retires rather than being extended.** It conflates *"was
this auto-resolved"* with *"is anyone watching to answer differently"*, and the
core engine's stack already recorded the consequence: with no resolver set at
all, an expert who authored a condition still gets no second chance in automatic
mode. That is one of the seven design threads still open on
`d-core-single-class`, and whichever way it is settled, the gate belongs on a
capability rather than on a mode.

**3. Literature recorded for a design-time review**, so the first session on
this does not start from scratch: blackboard knowledge-source activation
conditions, Contract-Net eligibility, and Chain-of-Responsibility's `canHandle`
for the guard; mixed-initiative and critiquing systems for the ensembles.

## Cross-plan dependencies, and what they cost

Both edges this track needs leave the plan, so `depends_on` cannot express
either and both are recorded as `blockers` instead — which means these items
carry no dependency chip and no automatic readiness computation:

- `expert-capability-guards` needs `d-core-single-class` (#159) in
  `rdr-core-engine`, whose condition resolver holds the `_try_auto_resolve`
  clauses being generalized.
- `expert-capability-verbalization` needs `rdr-why-answer` (#81) in
  `rdr-explanation`, whose rule-tree explanation machinery it reuses. It also
  needs `expert-capability-guards`, which is in this plan and keeps its edge.

The internal ordering is otherwise simple: the guard first, then the ensembles
and the verbalization in parallel.

## Open

- **Nothing here has a branch.** All three items are `blocked` on the core
  engine's stack landing.
- **Whether an ensemble arbitrates or composes** is undecided. "Hint mode as
  composition" states the shape for one case; what happens when two guards both
  pass and the experts disagree has not been designed.

## Standing conventions

- Follow `.claude/personal/cram-notes.md` and this repository's `AGENTS.md`.
- SOLID is a review gate: a new capability enters as an abstraction plus small
  dataclass implementations, and strategies stay substitutable without touching
  the engine. This track is unusually exposed to that rule, since its whole
  subject is making a dispatch decision substitutable.
- TDD: failing test first, and no test is modified to make something pass.
- `krrood` stays self-contained; world-like scenarios are mimicked in
  `test/krrood_test/dataset`.
- The programme's working method — run the probe rather than reasoning, compare
  sorted collected test ids rather than counts, stage by explicit path — is
  recorded in `rdr-core-engine`'s roadmap and applies here unchanged.
