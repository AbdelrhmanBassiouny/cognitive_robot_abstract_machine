# D-core-corner-case (#65): progress

2026-11-10 resolve: the item was stalled on four review threads from that morning, not on the 2026-09-30 integration-conflict label.

- Done (d2d7ceb990): `record` → `record_corner_case`, `get` → `get_corner_case_for_node`, a/an in `test_underspecified_match.py`. Callers renamed on D-core-serialization (d3e16a5569), D-core-single-class, D-core-engine and D-ui-rendering; stack restacked.
- Open: the thread on moving the case serializer to `krrood.code_generation` (proposal posted, waiting on the developer); the a/an sweep plus checker (proposed separately).
- CI on d2d7ceb990: 18/18 green. Not checked: the integration-conflict label (its combined tree no longer exists; no tool here re-runs it); the local suite (`pyjpt` won't install).
- The claude/rdr-why-answer-6fnw2o chain conflicts on explanation.py/observer.py independently of this change and still uses the old names.
