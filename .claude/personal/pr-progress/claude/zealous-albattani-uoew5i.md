PR #535, plan item eql-planning/fluent-state-overlay. Draft.

Plan:
- Fluents are EQL ground terms (attribute, index, call, predicate/symbolic function class); every EQL value path reads through EvaluationContext.term_reader; State implements TermReader.
- Scope per the hypothetical-states design (https://claude.ai/artifact/3zhr45pHQ9P9mdqxtJs5L5): value overlay only; objects in a state is the new item state-objects-and-domains.

Done:
- ground_term.py, State over ground terms, 32 tests; EQL/RDR/ORM suites pass locally.
- Design doc on Python bodies, objects and domains finalized; plan updated from it.

Next:
- Owner confirms the scope of #535.
- Merge main (15 behind); document in docstrings that a derived fact follows the state when its body is EQL or its inputs are EQL arguments; update the PR description's open decision to point to the design.
- Owner review; mark ready only when told.
