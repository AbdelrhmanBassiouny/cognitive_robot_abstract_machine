## Plan
- Keep the contract: for a SymbolicFunction class, `_type_` is what `__call__` returns and the class is `_factory_`. No silent `object` fallback: an unannotated factory raises ResultTypeCannotBeDetermined.

## Done
- `inference(factory)`, shared `_type_built_by_`, Match on classmethods (9a50802221).
- Nov 3 review: an() fix and krrood EQL agent rule (20b538ff1e); unannotated factories raise, callers annotated (f611cc5714).

## Next
- Wait for CI on f611cc5714.
- Owner answers: three `_type_` threads; factory-class pattern as a plan item or #513 discussion; field for the decorated symbolic function.
