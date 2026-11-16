## Plan
- Keep the EQL core free of random_events and probabilistic_model; probabilistic parts live in krrood.parametrization.

## Done
- Moves, lazy factories and import-boundary test landed; CI green (14/14) at 8285d6814a.
- Merged the updated main (docstring conflicts in backends.py, parameterizer.py) at 787d2ec478; pushed. CI on it not read yet.
- Upstream PR #985: 1/1 checks, no reviews or threads (read this run).
- Fork thread on probabilistic_queries.py resolved.

## Next
- Read CI at 787d2ec478 when it finishes.
- Open thread on test_grammar_registry.py: user asked whether a class-level flag should replace the module-binding filter in PhraseRuleRegistry.loaded_rules; awaiting the user's yes/no.
