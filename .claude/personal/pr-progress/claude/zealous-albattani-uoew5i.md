PR #535, plan item eql-planning/fluent-state-overlay (auto mode). Draft.

Plan:
- EQL reads attributes through EvaluationContext.attribute_reader (AttributeReader interface); new default contexts inherit the current reader.
- krrood.planning.state: Fluent (by identity) and a frozen State(AttributeReader) with with_assignments, eq/hash and as_current().

Done:
- Implemented; 11 tests in test/krrood_test/test_planning; the EQL, RDR and ontomatic suites pass locally (2 object-diagram failures: no graphviz binary here).
- PR description lists the open points: plain-Python reads bypass the overlay; only Attribute is hooked; no normalization of no-op assignments.

Next:
- Check CI on the PR; owner review, then mark ready.
