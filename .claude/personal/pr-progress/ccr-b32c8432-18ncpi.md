## Plan
- variable(Type, expression) / variable_from(expression): evaluate per binding, flatten, type-filter
- State: added/removed objects, a diff over the base SymbolGraph
- Default domains read from the evaluation's TermReader per evaluation (State or live SymbolGraph)
- No filtering of captured lists; values stay as given

## Done
- Branch and draft PR #541, stacked on #535 (merged into latest main; no force push)

## Next
- Tests first in test/krrood_test/test_planning and test_eql, then implementation
