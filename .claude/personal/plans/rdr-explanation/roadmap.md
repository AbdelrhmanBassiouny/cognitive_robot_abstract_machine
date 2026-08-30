# Why-questions on RDR conclusions — Roadmap

Narrative half of `rdr-explanation`. One of seven plans the oversized
`rdr-refactor` was split into on 2026-08-30; the predecessor's full 3,259-line
roadmap remains in the personal-notes branch's history immediately before that
split commit.

## What is being built

Explaining a conclusion the engine reached, and a demo that narrates its own
choices. This track was given priority over the feature layer, multi-tree
engines and truth unification by a decision on 2026-07-16.

- **`rdr-why-answer` (#81)** — `WhyQuestion`/`WhyAnswer` value objects built
  from `ClassificationTrace`/`FiredConclusion`, `EQLSingleClassRDR.why(case)`,
  the backend explain path, and `Explanation` unified with `explain_inference`.
  Plain "why" in version one; the contrast field is reserved, since a
  contrastive question is a follow-up expressed through `SufficientConditionSet`.
- **`eql-causal-verbalization` (#82)** — a "because" vocabulary and a
  `grammar/causal/` assembler following the existing `InferenceAssembler`
  pattern, routed beside the `Match` special case, with binding threading, so
  `WhyAnswer.verbalize()` works.
- **`rdr-why-query-surface` (#84)** — the `why(...)` EQL factory, the
  documentation and the bibliography. The `%why` magic waits on the interactive
  layer.
- **`rdr-decision-queries` (#85)** — the explanation semantics behind decision
  queries.
- **`explanation-rendering-by-audience`** — the same explanation rendered for
  whoever is receiving it.
- **`montessori-choice-policies`** and **`montessori-why-demo`** — the
  shape-sorting demo.

`eql-attribute-predicate-verbalization` (#83) has merged and is here because it
is the verbalization groundwork the causal grammar builds on.

## Decisions that still bind

**1. A choice *is* an underspecified query — the `ExplainableChoice` protocol
was dropped as YAGNI (2026-07-17).** A decision is
`an(InsertionAction)(slot=...).evaluate(backend=rdr)`: a partially specified
decision object whose missing attribute the RDR supplies. So
`rdr-decision-queries` delivers the *missing explanation semantics* rather than
a protocol — a model-side, weak-keyed explanation store, explanation-bearing
yielded results so `explain(result)` routes RDR conclusions, a default-on
explaining strategy subject to measuring first, a typed first-access failure,
and the documented decision-query pattern.

The store is weak-keyed and deliberately never attached to a shared concluded
value: enum members alias, so attaching an explanation to the value itself would
give every case that reached the same conclusion the first case's explanation.

**2. The pattern this depends on now works.** `RDRBackend` conforms to
`QueryBackend` and `evaluate` is `fill`'s eager completion, so
`an(InsertionAction)(slot=...).evaluate(backend=rdr)` runs today. That was the
open conformance question when this track was planned; it is settled in
`rdr-core-engine`.

**3. Verbalization does not decide the guard's shape, contrary to
expectation.** Both a polarity flag and a `Not()` wrapper serve this track
equally: `ConditionAssembler.predicate(comparator, *, negated=False)` is already
the `(expression, polarity)` pair, and the grammar's `Not…Rule` families render
a wrapped comparator by unwrapping it back into that same call. So the core
engine's decision to keep `GuardCondition.negated` costs this track nothing.

**4. Content is separated from rendering, chosen from the recipient's model.**
Natural language for a human, the raw EQL expression for a program. The
EQL-as-formal-derivation versus natural-language-gloss distinction is the same
one the TMS justifications in `rdr-engine-extensions` will need, so the two
should be designed with each other in view. Literature recorded for a
design-time review: user-tailored generation, Grice's maxims, relevance theory.

**5. Ordering.** `rdr-why-answer` → `eql-causal-verbalization` →
`rdr-why-query-surface`, sequential; `rdr-decision-queries` runs parallel to the
query surface, since both need only the causal grammar.

## Cross-plan dependency, and what it costs

`rdr-why-answer` stacks on `d-core-backend` (#210) in `rdr-core-engine` — the
backend is what the explain path reads through. `depends_on` cannot name an item
in another plan, so that edge is recorded as a `blocker` and the item carries no
dependency chip and no automatic readiness computation. The same applies in
reverse: `rdr-expert-framework`'s `expert-capability-verbalization` needs
`rdr-why-answer` and records it the same way, because it reuses the rule-tree
explanation machinery to answer *why can this expert handle this situation*.

## Open

- **The Montessori demo is deferred on an external branch.**
  `montessori-choice-policies` waits on `montessori_ijcai` being ready; only the
  demo-specific remainder is left, since the pick and hole policies are decision
  queries under the pattern above and need no policy-injection seam.
  `montessori-why-demo` is the narrated loop, a headless CI mode emitting the
  why-transcript, and a README.
- **Conflict watch.** That external branch modifies the same krrood
  verbalization files the causal grammar touches — `vocabulary/english.py`,
  `fragments/base.py`, `parts_of_speech.py` — plus `factories.py` and
  `predicate.py`. Whichever lands second reconciles.
- **Not to be confused with `montessori-eql-stack`.** That is a separate,
  live plan for the demo's interactive EQL console (autocomplete, where-is
  highlighting, event replay, voice questions). These two items are the
  *why*-demo and share no files with it.

## Standing conventions

- Follow `.claude/personal/cram-notes.md` and this repository's `AGENTS.md`.
- SOLID is a review gate: a new capability enters as an abstraction plus small
  dataclass implementations, and strategies stay substitutable without touching
  the engine.
- TDD: failing test first, and no test is modified to make something pass.
- `krrood` stays self-contained; world-like scenarios are mimicked in
  `test/krrood_test/dataset`.
- The programme's working method — run the probe rather than reasoning, compare
  sorted collected test ids rather than counts, stage by explicit path — is
  recorded in `rdr-core-engine`'s roadmap and applies here unchanged.
