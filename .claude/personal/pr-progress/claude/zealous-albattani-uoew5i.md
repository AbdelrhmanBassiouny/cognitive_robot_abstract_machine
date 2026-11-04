PR #535, plan item eql-planning/fluent-state-overlay. Ready for review (owner). Merges bug PRs #538 and #540 (off main).

Plan:
- Value overlay; facts are EQL conditions (State.with_facts); typed value terms built by GroundTermExpression[TermT]; queries take state=.

Done:
- adcb71821 owner review: CallSignature.of->from_callable; bind/bind_by_name take CallArguments; pass_to removed; no abbreviations in query_graph.

Next:
- Owner decides 2 open threads (pass_to removal, keep bind). Api-break note in #535 description (Call._arguments_, from_callable, bind/bind_by_name). Fork CI at adcb71821 unread; branch 40 behind main.
