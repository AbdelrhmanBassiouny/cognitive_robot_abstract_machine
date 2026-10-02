Branch claude/blissful-davinci-9fogks, stacked on claude/match-query-interface-refactor-l55jym (PR #192,
rebased onto its head 3bd091ff4). Draft PR #477 targets that branch; retarget to main once #192 lands.

Done (commit eaaccea93, pushed):
- Goal 1: generative backends construct from Bindings rows (Match._construct_instance_from_bindings_,
  AttributeMatch.construct_value_from_bindings, HasFactoryAndKwargs._factory_keyword_arguments_,
  EQL _enumerate_bindings, UnderspecifiedParameters.bindings_from_model_sample). UnboundPatternVariable.
- Goal 2 (user chose OperationResult subclass): ProbabilisticOperationResult; ProbabilisticBackend.sample_bindings,
  compute_log_likelihood, _resolve_model_to_sample; UnderspecifiedParameters.model_sample_from_bindings.
  ModelVariableNotBound.
- krrood 2090 passed (2 graphviz-dot env failures), probabilistic_model 656 passed.

- b85d0bdcb (user approved): removed _update_kwargs_from_literal_values, AttributeMatch._update_kwargs_from,
  _get_mapped_variable_by_name and their two tests; tests look up pattern variables via
  test/krrood_test/pattern_variables.py find_assigned_variable. krrood 2088 passed, pm 656 passed.
  PR description updated.
- 8d8dc1f2b merged #192's latest (25f86cc30, cram2 main). 83724f815 (user: fix in this PR):
  model_sample_from_bindings derives domain-object feature values via DomainObjectFeature kept while
  building the truncation event. krrood 2201 passed, pm 656 passed. PR description updated.
Open: object outside a pattern variable's domain fails with a plain ValueError (both directions).
Env note: the verification venv is .venv (uv 0.12 via pip; the system uv 0.8 cannot parse root pyproject);
full test runs regenerate test_verbalization/verbalization_results.py - restore before committing.
