Plan:
- Wait for the owner's answers on the two open fork threads and for fork CI on f59f1658.

Done (at f59f1658, pushed):
- ConditionEvaluation takes ConditionType and reads booleans through SymbolicExpression._as_operand_.
- Plan item typed-index-and-call-terms added (tracking issue #513). The earlier plan item shared-attribute-diff is in the plan too.
- test_eql (1634) and the planning tests pass; krrood check passes; the merge probe against main 66b057e1 is clean.
- Replied on all 4 new threads; resolved 2. PR description updated.

Next:
- Open, waiting on the owner: exceptions.py:190 (aggregator effects in action-application-query?) and evaluation.py:248 (does _as_operand_ answer "inside Literal"?).
- Upstream #1060: tomsch420 requested changes; the owner replies there.
