## Plan
- Answer the open thread on CI enforcing boundaries (reply posted, left for the developer).
- Decide whether `krrood.parametrization.__init__` should keep importing the grammar eagerly.

## Done (read at 6f9e035fd7)
- Regression fixed: the symbol graph's type-hint scope now defers TYPE_CHECKING imports (`DeferredImportScope`), so building a clause loads no realization library.
- Negation and number are each asked in one place (`PolarRealization`, `AgreeingRealization`); the two new review threads are resolved.
- 917 verbalization, class-diagram and core-boundary tests pass; `krrood check` clean on touched files.

## Next
- CI checks on the new head were not read yet.
- Developer: the `as_fragment` rename and the rest of `test_eql` / `semantic_digital_twin` were not run.
