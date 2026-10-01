## PR #479 — probability as an operand (stacked on #192)

Branch `claude/probability-as-operand`, draft, base `claude/match-query-interface-refactor-l55jym`.

Done 2026-10-01 (`bf5a5891f`): `ProbabilityValue` node (child = count ratio), `Probability` is
`HasSymbolicOperations[float]` (comparisons both sides, `_is_own_name_` claims underscore names),
`ProbabilityValueRule` verbalizes it as the probability. Doc section added. krrood 2082 passed.

Open, for the developer: a nested probability is always counted, never resolved through the
model under `ProbabilisticBackend` (would need the model registry passed into nested evaluation).
Measured: a domain-less variable counts its live instances (count 1), so no 0/0 bug exists.

Next: nothing to push; retarget onto `main` once #192 lands.

Review round 2026-10-01 (three fork threads):
- `_is_own_name_` (resolved, 1cfe19915): base `HasSymbolicOperations` owns every name its MRO
  declares (vars or annotations); new `ReservesFrameworkNames` (Match, Probability) adds `_name_`
  form. Single-underscore private attributes now go to the value type. #192's TypeError commit
  merged in (17c64646e). krrood 2089 passed.
- Probability as an Aggregator (line 90) and whether `ProbabilityValue` is then needed (line 176):
  open, discussing in session. Measured: a selected condition yields True/False per row, so
  probability = mean of the condition; a scratch `Aggregator` subclass gives correct per-group
  values (current #479 gives the global 0.75 repeated per group - a real bug) and works in
  `having`; but every aggregator is refused in another query's `where`
  (`AggregatorInWhereConditionsError`), so `t.value < probability_of(...)` would need
  `entity(...)` around it, like `average`. Awaiting the developer's decision.
