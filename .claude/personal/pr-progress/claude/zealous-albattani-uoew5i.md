PR #535, plan item eql-planning/fluent-state-overlay. Promoted as cram2#866: changes requested (tomsch420, LucaKro).

Plan:
- Value overlay; facts are EQL conditions (State.with_facts); typed ground terms built by GroundTermExpression; queries take state=.

Done:
- 35b00d72ca: merged #862 from main (terms built from _factory_); tuple index facts accepted; planning docstrings formatted.

Next:
- Owner answers 3 cram2#866 design threads (fluent vocabulary, owner identity, state= on other backends); then implement and draft upstream replies.
- Fork threads left for the owner: pass_to removal, keep bind, TermValue (kept).
