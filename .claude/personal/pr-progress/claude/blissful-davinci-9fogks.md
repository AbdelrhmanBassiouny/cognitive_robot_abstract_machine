Branch claude/blissful-davinci-9fogks, stacked on claude/match-query-interface-refactor-l55jym (PR #192).
Draft PR targets that branch, not main.

Done:
- Goal 1: Match._construct_instance_from_bindings_ + AttributeMatch.construct_value_from_bindings
  (leaf values via _evaluate_ under OperationResult(bindings)); HasFactoryAndKwargs keyword
  filtering split into _factory_keyword_arguments_; EQL generative backend enumerates
  set_of rows remapped to pattern-variable ids; UnderspecifiedParameters.bindings_from_model_sample
  replaces construct_instance_from_model_sample. UnboundPatternVariable exception.
- Goal 2 (user chose OperationResult subclass): ProbabilisticOperationResult(log_likelihood)
  in krrood/parametrization/probabilistic_operation_result.py; ProbabilisticBackend.sample_bindings,
  compute_log_likelihood, _resolve_model_to_sample; UnderspecifiedParameters.model_sample_from_bindings
  (inverse; stated literals fill conditioned variables); ModelVariableNotBound exception.
- Targeted tests green; formatted with scripts/format_docstrings.py.

Next: full krrood + probabilistic_model suites, commit, push, open draft PR (base = PR #192 branch).
Open questions for user: _update_kwargs_from_literal_values / AttributeMatch._update_kwargs_from /
_get_mapped_variable_by_name now only used by tests - remove? Likelihood of a match with a
non-primitive krrood variable (identifier + feature variables) raises ModelVariableNotBound
(feature values not derived from the bound object).
