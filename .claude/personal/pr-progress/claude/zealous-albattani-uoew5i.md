PR #535, plan item eql-planning/fluent-state-overlay. Draft. Merges bug PR #538 (off main).

Plan:
- Value overlay; facts are EQL conditions (State.with_facts); typed value terms built by GroundTermExpression[TermT]; queries take state=.

Done:
- Review round 3 (a357071dd): EvaluationContext.iterate_reading_from, doctest examples; append recorded under action-schema-progression.

Next:
- Plan item instantiated-variable-type-and-factory: PR off main, merge into #535.
- Owner: answer 5 open threads (assigned_functions frozenset, ResultType bound, GroundTerm __eq__, predicate-wrapped inequality); mark ready only when told.
