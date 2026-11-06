PR #535, plan item eql-planning/fluent-state-overlay. Promoted as cram2#866: changes requested (tomsch420, LucaKro).

Plan:
- Value overlay; facts are EQL conditions (State.with_facts); typed ground terms built by GroundTermExpression; queries take state=.

Done:
- c1e7fc3c0a: cram2#866 answers: fluent defined in planning; owners by identity (ObjectIdentity); BackendCannotReadState.
- 67ec08bf21: krrood/conftest.py keeps live logging out of doctests (State doctest fixed).
- 11833ae887: Nov 6 fork review: fluent defined in State docstring; _first_argument_is_receiver; replies inline.

Next:
- Owner decides open fork threads: argument comparison by value (test_ground_term.py:33), shared doctest plugin, from_call form, rename; older pass_to/bind/TermValue.
- Owner posts drafted cram2#866 replies; re-review. CI on 11833ae887 not checked.
