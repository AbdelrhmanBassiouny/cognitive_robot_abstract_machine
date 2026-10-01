## PR #479 — probability as an operand (stacked on #192)

Branch `claude/probability-as-operand`, draft, base `claude/match-query-interface-refactor-l55jym`.

Done 2026-10-01 (`bf5a5891f`): `ProbabilityValue` node (child = count ratio), `Probability` is
`HasSymbolicOperations[float]` (comparisons both sides, `_is_own_name_` claims underscore names),
`ProbabilityValueRule` verbalizes it as the probability. Doc section added. krrood 2082 passed.

Open, for the developer: a nested probability is always counted, never resolved through the
model under `ProbabilisticBackend` (would need the model registry passed into nested evaluation).
Measured: a domain-less variable counts its live instances (count 1), so no 0/0 bug exists.

Next: nothing to push; retarget onto `main` once #192 lands.
