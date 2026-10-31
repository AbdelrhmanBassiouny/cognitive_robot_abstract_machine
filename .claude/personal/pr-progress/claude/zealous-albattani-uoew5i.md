PR #535, plan item eql-planning/fluent-state-overlay. Draft. Merges bug PR #538 (off main).

Plan:
- Value overlay; facts are EQL conditions (State.with_facts); typed value terms built by GroundTermExpression[TermT]; queries take state=.

Done:
- Review round 2 (d52af4309): 12 threads resolved, 6 replied and left open; 39 planning tests; test_eql passes.

Next:
- Separate PR off main: InstantiatedVariable type field (always a type) plus factory field; merge into #535.
- Owner: answer the 6 open threads (try-except, list append, predicate-wrapped inequality, State(f1, ...), the(b) facts, type/factory); mark ready only when told.
