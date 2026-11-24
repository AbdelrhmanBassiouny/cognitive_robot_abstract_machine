## Plan
- Resolve the owner's first review of #617 (21 threads at 38610d26), with the owner's Nov 24 decisions.

## Done
- 484d201e: ActionSchema and Effect only build queries; State evaluates (apply_effects, apply_action, satisfies). Insertions are their own change; private Symbol._persist_instance_.
- 8deedde0: ConditionEvaluation replaces evaluate_statements_of; apply_action evaluates the precondition once and reports the failed conditions from that evaluation.
- Replied to all 21 threads, resolved 17; new plan item planning-query-verbalization.

## Next
- Owner answers 4 open threads: __init_subclass__ variables, the composed query, a value-type GroundTermExpression, conditional effects.
- Check fork CI at 8deedde0.
