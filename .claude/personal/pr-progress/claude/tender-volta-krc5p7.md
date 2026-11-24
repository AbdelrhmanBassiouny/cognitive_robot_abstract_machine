## Plan
- Resolve the owner's first review of #617 (21 threads at 38610d26), with the owner's Nov 24 decisions.

## Done
- 484d201e: ActionSchema and Effect only build queries; State evaluates (apply_effects, apply_action, satisfies).
- Insertions are a CollectionInsertion change; private Symbol._persist_instance_; ActionIsNotApplicable.failed_conditions.
- Added the requested test assertions and docstring rewordings; replied to all 21 threads and resolved 17.
- New plan item planning-query-verbalization (#513 comment).

## Next
- Owner answers 4 open threads: __init_subclass__ variables, the composed query, a value-type GroundTermExpression, conditional effects.
- Check fork CI at 484d201e.
