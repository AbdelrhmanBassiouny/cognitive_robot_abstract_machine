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
- Probability as an Aggregator (line 90) and `ProbabilityValue` (line 176): developer chose the
  aggregator. Done in 86dca40db, both threads replied+resolved. `Probability(ProbabilisticQuery,
  Aggregator[float])`, child = condition, truths read from the condition's own binding (a logical
  operator's value is its whole row - `and_` gave 1.0 otherwise). Grouped = per-group probability
  (test failed before). `ProbabilityValue` + rule removed. Probability no longer claims `_name_`
  names (variable-like); that test removed. #480 merged in (1332f33d3) so a nested probability in
  a where reads as a subquery. krrood 2094 passed.

Landing order: #192 and #480, then #479. Next: nothing pending; retarget onto main once they land.
