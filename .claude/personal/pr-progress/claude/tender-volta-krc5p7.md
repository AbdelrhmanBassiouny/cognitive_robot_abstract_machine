Plan (resolve of the Nov 25 review, at 528fddac):
- Rename ActionSchema to AssertiveKnowledgeAction, module included (owner decision).
- Rename Effect.get_change_to_state to get_change_to_state_query (owner decision).
- Handle bool conditions in EQL's ConditionEvaluation, not in State.
- accepts_element: False for a field that declares no collection; tests for numbers.Real/Integral fields.
- Reword ConflictingAssignments.suggest_correction.
- Fix the fork CI's krrood check findings: docstrings, with_objects_added/removed renamed to add_objects/remove_objects.
- Reply inline on every fork thread; resolve those that are done.
- Add a plan item to share one added/removed-elements diff with JSONAttributeDiff (upstream review, tomsch420).

Done:
- Stack pass clean; merge probe CLEAN at 528fddac; baseline 146 tests pass.

Next:
- Implement, test, push through maintenance push, and update the PR description and plan notes.
