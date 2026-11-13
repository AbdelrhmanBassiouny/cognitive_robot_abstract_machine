## Plan
- EQL imports no random_events/probabilistic_model; probabilistic parts live in krrood.parametrization

## Done
- number_like_field plain check; fresh-interpreter import-boundary test
- ProbabilisticBackend, causal search results, probabilistic queries + factories + rules moved; importers rewritten
- Lazy grammar (PhraseRuleRegistry.loaded_rules), only rule classes their module binds
- krrood check clean vs base; test_eql 1561 passed; PR #609 description/labels current

## Next
- Await review; rebase when #545 or #608 (classproperty move touches backends imports) lands
- semantic_digital_twin/coraplex/experiments suites only verifiable in CI
