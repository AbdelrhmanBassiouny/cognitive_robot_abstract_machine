# PR plan: rdr/general-fixpoint — GRDR fixpoint engine (Wave 1, Track G, PR 2/2)

Not started. Base: `rdr/multi-class`. Design: `rdr_architecture_plan.md`
§2.2–2.3 (Datalog grounding).

## Goal

`GeneralRuleTreeEngine`: evaluate a set of RDR trees to fixpoint, feeding
conclusions back as case attributes (naive Datalog evaluation), with the
contracts that make Wave 2 (concept trees) safe designed in from day one:

- **Monotonic conclusions:** rules only add conclusions, never retract
  another tree's output. Enforced by the conclusion store, raising a
  custom exception on violation.
- **Recorded dependency edges:** whenever tree B's conditions read a
  conclusion produced by tree A, record edge A → B (extractable from which
  conclusion attributes the conditions reference). Stored in a
  `DependencyGraph` value object — Wave 2 consumes it for stratification
  and impact analysis.

## Design (SOLID)

- `EvaluationStrategy` ABC with `NaiveFixpoint` as the first
  implementation; `SemiNaiveFixpoint` arrives in Wave 2 as a drop-in
  (OCP/LSP — the engine never changes).
- Conclusion storage: engine-side blackboard keyed by (case, attribute),
  NOT mutation of the user's dataclass (keeps definitions pure; the open
  question in the plan §5 — decide here, document why).
- The engine owns a set of `EQLRuleTreeClassifier`s (the Track-G-PR-1
  abstraction) — it does not know single- vs multi-class.

## TDD sequence

1. Failing test: two trees where B's condition reads A's conclusion —
   naive loop converges in 2 passes, conclusions correct.
2. Failing test: retraction attempt raises the monotonicity exception.
3. Failing test: dependency edge A → B is recorded and queryable.
4. Convergence guard: mutually-dependent trees (A ↔ B) still terminate
   (monotonicity ⇒ fixpoint) — pin with a test.
