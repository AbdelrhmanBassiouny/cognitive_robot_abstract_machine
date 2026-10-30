PR #535, plan item eql-planning/fluent-state-overlay. Draft.

Plan:
- Value overlay only (owner confirmed Oct 30): ground-term fluents read through EvaluationContext.term_reader; State implements TermReader. Objects in a state is the separate item state-objects-and-domains.

Done:
- ground_term.py, State, 33 tests; main merged (3bf731b5b9); contract for derived fluents documented on State and tested; test_planning and test_eql pass locally.

Next:
- Owner review; mark ready only when told.
