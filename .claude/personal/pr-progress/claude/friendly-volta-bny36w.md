## Plan
- Fresh-interpreter test: every EQL module imports with random_events/probabilistic_model blocked
- Move causal result dataclasses, ProbabilisticBackend, probabilistic_queries (+ distribution_of/probability_of, their verbalization rules) to krrood.parametrization
- Verbalization rules collected lazily from every loaded PhraseRule subclass (user-chosen)
- Update imports in tests, docs, other packages; run EQL/parametrization tests

## Done
- PR #609 opened on #545's branch; item recorded in progress
- number_like_field is a plain int/float-not-bool/Enum check, with tests

## Next
- Write the import-boundary test, then the moves
