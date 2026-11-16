## Plan
- Keep the EQL core free of random_events and probabilistic_model; probabilistic parts live in krrood.parametrization.

## Done
- Moves, lazy factories and import-boundary test landed; CI green (14/14) at 8285d6814a.
- Merged updated main at 787d2ec478; replaced the module-binding filter with PhraseRule.joins_grammar (default True) at d27b63faeb (user chose opt-out); pushed. Not run under pytest here (random_events build mismatch).
- Upstream PR #985: 1/1 checks, no reviews or threads (read this run).
- Fork thread on probabilistic_queries.py resolved.

## Next
- Read CI at d27b63faeb; if green, resolve the test_grammar_registry.py thread.
