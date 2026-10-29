PR #535, plan item eql-planning/fluent-state-overlay (auto mode).

Plan:
- EQL: an AttributeReader interface with a live default; EvaluationContext.attribute_reader; Attribute reads through it; nested new contexts inherit the reader.
- krrood.planning.state: Fluent (identity of the instance) and a frozen State(AttributeReader) with with_assignments, equality and hash over assignments, and as_current().
- Tests first in test/krrood_test/test_planning against a blocksworld mimic.

Done:
- Bootstrap commit, draft PR, manifest set to in progress.

Next:
- Write the failing tests, then the EQL hook, then State.
