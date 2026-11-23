## Plan
- Facts take expression values, bound in the state they extend; drop FactValueIsNotConstant
- Type-check assigned attribute values against the class diagram (AssignedValueHasWrongType)
- Effects: Assignment, Append, ObjectCreation, ObjectRemoval, each optionally conditional, combined against the predecessor state
- ActionSchema: precondition/effects on a symbolic twin; is_applicable, apply, applicable_actions
- Tests first, in test/krrood_test/test_planning with a Symbol-based blocks mimic

## Done
- Branch, draft PR #617, item recorded in progress

## Next
- Failing tests for facts with expression values and the type check
