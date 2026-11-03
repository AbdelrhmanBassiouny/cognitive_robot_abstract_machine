## Plan
- Owner answers the three open threads (plan_transformations.py:334, task_conditions.py:477, planner.py:118) on why `_factory_` and not `_type_`.

## Done
- Every review ask is implemented. CI is green on d6e043762c (all 18 checks).
- An upstream link has been recorded under `## Promote`, and no upstream PR exists yet.

## Next
- Once confirmed, resolve the three threads. If the owner says so, switch those readers to `_type_` and reverse the "one result-type field" contract.
- After this merges, #535 drops `Fact._is_predicate`'s `isinstance(_type_, type)` guard.
