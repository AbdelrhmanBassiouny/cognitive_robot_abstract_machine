# EQL core and the code_generation extraction — Roadmap

Narrative half of `eql-core-and-code-generation`. One of seven plans the
oversized `rdr-refactor` was split into on 2026-08-30; the predecessor's full
3,259-line roadmap remains in the personal-notes branch's history immediately
before that split commit.

## Why this is its own plan

These six items are the layer *under* the RDR engine, not part of it. Four are
the EQL core and the extraction of `krrood.code_generation` out of
`ripple_down_rules`; the other two are core-semantics fixes that landed
alongside. Everything in `rdr-core-engine` and above was built on them, and all
six have merged, so this plan is the record of what the foundation settled
rather than a queue of work.

## What each item settled

- **`query-class-refactor` (#5)** — the spec/product lifecycle and subquery
  caching in the query classes.
- **`eql-core-prep` (#28)** — the core semantics the RDR engine needed before
  it could be an `EvaluationObserver` over EQL evaluation.
- **`code-extraction` (#58)** and **`code-generation-extract` (#39)** — source
  extraction and generation pulled into `krrood.code_generation`, a package of
  its own rather than utilities inside the RDR package.
- **`conditions-root-drop-dead-parent-recovery` (#89)** — `_conditions_root_`'s
  use of `_last_parent_of_type_` was genuinely dead, verified by instrumenting
  it across 1,275 tests for zero calls, so the method went. That is distinct
  from the *live* use of the same method name for `insert_at`'s anchor-parent
  recovery, which was a real bug and is fixed at the façade level by
  `dag-facade-hardening` instead.
- **`eql-truth-unification` (#99)** — `OperationResult.is_false` dropped, truth
  read from `bindings[operand._id_]`, `is_condition_false` retired.

## Decisions that still bind

**1. Truth is filtered only at truth-recording roots.** The design document's
invariant, taken verbatim, dropped query results whose value was `0` or empty,
because for entities, aggregators and arithmetic the single binding *is* the
selected value. `TruthValuedExpression` tells the two kinds of expression apart
and only truth-recording roots are filtered by truth. Anything later that
reasons about `_true_results_()` inherits this distinction.

**2. The field was removed outright, not transitioned through a flag.** A
missed call site then fails loudly rather than silently compiling.
`_evaluate_child_as_condition_` was kept as a pass-through so the dependent
recording hooks survive.

**3. `...` is a value inside the space, not a sentinel outside it.** `CountRange`
already counts `value is ...` over evaluated results and widens an `int` to a
closed interval, so EQL deliberately puts "not yet determined" *inside* the
value space and reasons about it. This is what later let the RDR's `UNSET` be
replaced by `...` outright: the sentinel means *an oracle must supply this
value*, and it does not matter whether the oracle is a human, a probabilistic
model or an RDR.

## The hazard this plan is the case study for

**A file neither side's diff touches is where a merge is silent and wrong.**
`D-core-serialization` renamed `type_hints.py` to `object_to_source.py` and
claimed to update every importer; `template_file_creator.py` imported the
deleted module, was touched by neither side, and git's rename-aware merge kept
it pointing at nothing. It surfaced as a red CI run, not as a conflict. The same
mechanism then recurred twice more in this programme — a deleted `rdr/utils.py`,
and a renamed `aid.py` — so the standing check after any restack is to import
the package, not to count conflicts.

## Standing conventions

- Follow `.claude/personal/cram-notes.md` and this repository's `AGENTS.md`.
- SOLID is a review gate: a new capability enters as an abstraction plus small
  dataclass implementations, and strategies stay substitutable without touching
  the engine.
- TDD: failing test first, and no test is modified to make something pass.
- `krrood` stays self-contained; world-like scenarios are mimicked in
  `test/krrood_test/dataset`.

## Open

Nothing. Every item has merged. The plan is kept because the decisions above are
read by `rdr-core-engine` and `rdr-engine-extensions`, and because deleting the
record would leave those plans citing merged pull requests with no statement of
what they settled.
