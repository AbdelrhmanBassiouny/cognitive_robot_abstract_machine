## Plan
- Keep the contract: for a SymbolicFunction class, `_type_` is what `__call__` returns and the class is `_factory_`.

## Done
- `inference(factory)` takes only the factory. `HasFactoryAndKwargs._type_built_by_` infers the type for Match and InstantiatedVariable, and a Match on a classmethod now gets the class it returns (9a50802221).
- The plan no longer says #542 merges into #535. #535 stacks on it if it needs it.

## Next
- Wait for CI on 9a50802221.
- Owner answers the three `_type_` threads.
