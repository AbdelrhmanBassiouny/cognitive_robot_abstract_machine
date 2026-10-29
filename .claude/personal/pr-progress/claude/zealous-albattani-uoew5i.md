PR #535, plan item eql-planning/fluent-state-overlay. Draft.

Plan:
- Fluents are EQL ground terms (attribute, index, call, predicate/symbolic function class); every EQL value path reads through EvaluationContext.term_reader; State implements TermReader.

Done:
- ground_term.py (symbols, GroundTerm with normalized arguments, TermReader); State over ground terms; 32 tests; main merged; EQL/RDR/ORM suites pass locally.

Next:
- Owner decides how Python bodies of predicates/symbolic functions see the state (arguments, proxies, or mutate-and-undo; see PR).
- Owner review; mark ready only when told.
