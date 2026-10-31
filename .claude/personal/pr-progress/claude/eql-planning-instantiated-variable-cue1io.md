# instantiated-variable-type-and-factory (#542)

## Plan
- _type_ = result type (always a type), _factory_ = builder (defaults to _type_).
- Callers: inference(type_, factory=None), @symbolic_function, SymbolicCallable._bound_value_type_.
- Operation readers (verbalization, coraplex, experiments) read _factory_.

## Done
- Implemented and pushed (b0d12c688); 11 new tests; test_eql 1443 passed.
- PR description lists decisions and migration.

## Next
- Owner review of the decisions (object fallback, generic origin, factory stays the class).
- After merge into #535: drop Fact._is_predicate's isinstance(_type_, type) guard there.
