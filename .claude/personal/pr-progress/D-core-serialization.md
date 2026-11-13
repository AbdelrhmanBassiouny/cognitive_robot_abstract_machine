Plan
- Keep #66 ready; react to the owner's next review.

Done
- 9b48605708 (round 3): ast_constant dropped, applies -> can_emit_source_for_object, factory imports pruned by Ruff (remove_unused_imports), default SourceEmitter.family, connectives emit left/right, NoApplicableSourceEmitterError default, MissingAddConclusionError in rdr.exceptions. D-deco 495c210bb6 prunes the empty-tree template too.
- Carried down all nine descendants; all 2026-11-13 threads answered and resolved; PR description current.

Next
- Read CI at 9b48605708; the owner removes the integration-conflict label.
- Separate fix: DecomposedRuleTree fails on next_rule branches (Next has no .right).
- Descendants keep pre-existing keyword-only failures (ExpertAbort, insert_at, Match.from_, _iter_descendants_).
