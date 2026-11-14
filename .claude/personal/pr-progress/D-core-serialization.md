Plan
- Keep #66 ready; react to the owner's next review.

Done
- 22f35dfa26 (round 4): SpecificityRankedAlternative (guard + specificity class properties); SpecificityRule = guard applies; SourceEmitter selects via most_applicable (guard can_emit_source_for_object, rank by emitted type); classproperty moved to patterns/classproperty.py, re-exported by ormatic.utils.
- Carried down all nine descendants; both round-4 threads answered and resolved; PR description current.

Next
- Read CI at 22f35dfa26; the owner removes the integration-conflict label.
- Separate fix: DecomposedRuleTree fails on next_rule branches (Next has no .right).
- Descendants keep pre-existing keyword-only failures (ExpertAbort, insert_at, Match.from_, _iter_descendants_).
