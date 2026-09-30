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

Open for user: remove test-only _update_kwargs_from_literal_values / _update_kwargs_from /
_get_mapped_variable_by_name? compute_log_likelihood does not derive feature values for
non-primitive krrood variables (raises ModelVariableNotBound).
Env note: the verification venv is .venv (uv 0.12 via pip; the system uv 0.8 cannot parse root pyproject);
full test runs regenerate test_verbalization/verbalization_results.py - restore before committing.
