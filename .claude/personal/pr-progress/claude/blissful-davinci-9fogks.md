Branch claude/blissful-davinci-9fogks. #192 landed; draft PR #477 now targets main.

Done (all pushed):
- eaaccea93 Goal 1: generative backends construct from Bindings rows (Match._construct_instance_from_bindings_,
  AttributeMatch.construct_value_from_bindings, HasFactoryAndKwargs._factory_keyword_arguments_,
  EQL _enumerate_bindings). UnboundPatternVariable.
- eaaccea93 Goal 2 (user chose OperationResult subclass): ProbabilisticOperationResult; ProbabilisticBackend.sample_bindings,
  compute_log_likelihood, _resolve_model_to_sample; UnderspecifiedParameters.model_sample_from_bindings. ModelVariableNotBound.
- b85d0bdcb (user approved): removed _update_kwargs_from_literal_values, AttributeMatch._update_kwargs_from,
  _get_mapped_variable_by_name; tests use test/krrood_test/pattern_variables.py find_assigned_variable.
- 83724f815 (user: fix in this PR): model_sample_from_bindings derives domain-object feature values (DomainObjectFeature).
- 77030a7aa merged origin/main (ca2f620e1; user had pushed c6190b05e merging an older main). Conflicts in
  backends.py / parameterizer.py / factory_and_kwargs.py: main's batched SampleColumn now binds assigned_variable._id_;
  bindings_from_model_samples replaces construct_instances_from_model_samples and bindings_from_model_sample;
  _attribute_match_of keeps main's AmbiguousVariableName check for both directions. Updated main's
  test_answer_construction.py call to the new name (assertions unchanged).
  krrood 2308 passed, pm 944 passed (2 graphviz-dot env failures). PR description updated.
Open: object outside a pattern variable's domain fails with a plain ValueError (both directions).
Env note: the verification venv is .venv (uv 0.12 via pip; the system uv 0.8 cannot parse root pyproject);
krrood on main imports casadi undeclared - installed casadi~=3.7.0 into .venv; uninstall pytest-qt/pytest-xvfb after
reinstalls; full test runs regenerate test_verbalization/verbalization_results.py - restore before committing.
