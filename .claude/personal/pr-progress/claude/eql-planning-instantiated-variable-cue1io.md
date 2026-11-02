## Plan
- Keep the contract: for a SymbolicFunction class, `_type_` is the type `__call__` returns, and the class is `_factory_` (owner confirmed).

## Done
- InstantiatedVariable inherits HasFactoryAndKwargs (72aefdb9b2).
- An `Any` return annotation gives the type `object` (1b09ff3302). The test compares variables by identity, not `==`.
- The experiments test reads `_factory_` (d6e043762c, owner approved).
- Threads: the mixin and `==` threads are resolved. The three `_type_` threads are answered and left open.

## Next
- CI on d6e043762c.
- #535 merges this branch, then drops Fact._is_predicate's isinstance guard.
