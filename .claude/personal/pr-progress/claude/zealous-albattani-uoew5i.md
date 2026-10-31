PR #535, plan item eql-planning/fluent-state-overlay. Draft. Merges bug PRs #538 and #540 (off main).

Plan:
- Value overlay; facts are EQL conditions (State.with_facts); typed value terms built by GroundTermExpression[TermT]; queries take state=.

Done:
- 86eb30b38: Fact raises AssignmentBypassesSetter for fluents set by a setter, __setattr__ or __setitem__; CallTerm compares arguments through CallArguments (#540), unhashable ones by identity.

Next:
- Plan item instantiated-variable-type-and-factory: PR off main, merge into #535.
- Re-merge #540 if it changes; owner reviews; mark ready only when told.
