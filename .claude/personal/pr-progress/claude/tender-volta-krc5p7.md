## Plan
- ActionSchema, effects (Assignment, ElementInsertion, ObjectCreation, ObjectRemoval), facts with expression values, class-diagram type check

## Done
- Implemented and pushed (38610d26e); 98 planning tests, 1710 EQL/class-diagram tests, doctests and pre-commit pass
- Owner decision: State.with_facts renamed to State.add_facts; with_change named apply_change
- PR #617 description and labels (new-feature, api-break) current

## Next
- Owner review of the draft; discuss the add_facts rename with eql-planning-robots (#522)
- test_quantifier_overload_types.py not run locally (no mypy)
