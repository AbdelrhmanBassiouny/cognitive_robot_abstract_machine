Branch claude/blissful-davinci-9fogks, stacked on claude/match-query-interface-refactor-l55jym (PR #192).
Draft PR targets that branch, not main.

Plan:
1. Goal 1 (TDD): generative backends construct instances from Bindings rows instead of
   writing Literal._value_ / Match._kwargs_. Match.construct_instance_from_bindings +
   AttributeMatch.construct_value_from_bindings (leaf values via _evaluate_ under
   OperationResult(bindings)); EQL generative backend enumerates set_of rows remapped to
   pattern-variable ids; UnderspecifiedParameters.bindings_from_model_sample replaces
   construct_instance_from_model_sample.
2. Goal 2: likelihood-carrying row. Ask user: OperationResult subclass vs field
   (Bindings is a dict alias; `|` merge drops a dict subclass).
3. Run krrood suite + probabilistic_model tests, format_docstrings, open draft PR.

Done: env setup started (.venv, pip). Next: failing tests.
Open question for user: _update_kwargs_from_literal_values only used by one test after refactor.
