## Plan
- Keep the contract: for a SymbolicFunction class, `_type_` is what `__call__` returns and the class is `_factory_`. An unannotated factory raises ResultTypeCannotBeDetermined; `-> Self` on a method gives the class it is bound to.

## Done
- `inference(factory)`, shared `_type_built_by_`, unannotated factories raise (to f611cc5714).
- CI fixes: Self-returning factory methods, compute_euclidean_planar_distance annotated (d20cc9d808); `_declared_factory_` (d019c307c7).
- Factory-class pattern -> plan krrood-patterns (#552); a/an checker -> eql-verbalization/article-agreement-check.

## Next
- Wait for CI on d019c307c7.
- Owner answers: the three "why not `_type_`" threads.
