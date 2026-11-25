## Plan (owner review at 8deedde0)
- `an(inference(...))` without `entity` in `applicable_actions`.
- Rename `CollectionInsertion.followed_by` to `extend`.
- `GroundTermExpression` generic over its value type too; type `ElementInsertion.collection` with it.
- `State.satisfies` -> EQL `evaluate_condition(condition, state=)`.
- `Fact.ground_term` for a fact on literals; simplify the failed-condition tests.
- AGENTS.md rule: no multi-step access paths; a direct accessor instead.
- Reply: `apply_effects` as a query -> `planning-query-verbalization`; chained effects = derived fluents (ramification).

## Done
- Read at 8deedde0: CI green, merge probe clean, no upstream PR.

## Next
- Implement, test, push, reply on threads.
