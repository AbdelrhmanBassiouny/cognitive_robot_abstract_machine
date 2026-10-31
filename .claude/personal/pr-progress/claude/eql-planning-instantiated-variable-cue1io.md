# instantiated-variable-type-and-factory (#542)

## Plan
- Tests first: _type_ is always a type, _factory_ defaults to it, symbolic functions get a return-annotation type.
- InstantiatedVariable: _type_ (result type) + _factory_ (builder); readers of the operation switch to _factory_.
- Callers: inference, @symbolic_function, SymbolicCallable/SymbolicFunction.
- Run test_eql, verbalization, coraplex/experiments readers.

## Done
- Branch, draft PR #542, manifest record.

## Next
- Write the failing tests.
