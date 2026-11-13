Plan
- Finish the 2026-11-13 review of serialization.py (the HasFactory part is still open).

Done
- 5555b4359c: serialization.py now uses RuleTreeSourceEmitter and RDRSerializer; the constants are class properties or RDRModuleAttribute; the decomposition moved to rules/decomposition.py; literal and comparison-operator helpers moved to ast_helpers; generated source unchanged.
- Carried into all nine descendants (support, engine, expert, single-class, backend, ui-rendering, ui, store, deco); each was pushed with no new failures.
- Four review threads answered and resolved.

Next
- Owner: decide on HasFactory (thread r4561012001). It needs the type→factory registry or a factories restructure because of the import cycle.
- Read CI at 121ddadd9a; the owner removes the integration-conflict label.
- Descendants still have failures from main's keyword-only migration (ExpertAbort, insert_at, Match.from_, _iter_descendants_; test_rule_tree_growth on support and engine).
