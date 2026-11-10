# D-core-corner-case (#65): progress

## Plan
- Wait for the developer's next review round; nothing is open on #65.

## Done
- 2026-11-10: all review threads answered and resolved. Serializer moved to `krrood.code_generation.dataclass_source` (8d5d547330); `from_data` removed at the developer's choice (5330bfea28; D-ui-rendering tests 828d5f519e). Stack restacked through D-deco.

## Next
- Read CI on 5330bfea28 (not read yet).
- Not checked: the integration-conflict label (its combined tree no longer exists); the local suite (`pyjpt` won't install).
- The claude/rdr-why-answer-6fnw2o chain conflicts on explanation.py/observer.py on its own and lacks this round's changes.
- #66's test_serialization.py imports `what_do_we_know_about`, which #66 no longer defines (pre-existing).
