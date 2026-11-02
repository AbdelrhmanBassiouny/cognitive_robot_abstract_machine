## Plan
- Answer the four #542 review threads (resolve session, auto mode).

## Done
- InstantiatedVariable inherits HasFactoryAndKwargs (72aefdb9b2); the thread on core/variable.py is resolved.
- Answered the three `_type_` threads (coraplex, experiments, planner.py) and left them open: for a SymbolicFunction class, `_type_` is the return type of `__call__`.

## Next
- The owner's answer on the three open threads. If `_type_` should stay the class for SymbolicFunctions, revisit `_bound_value_type_`.
- #535 merges this branch, then drops Fact._is_predicate's isinstance guard.
