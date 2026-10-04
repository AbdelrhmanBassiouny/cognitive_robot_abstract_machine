## claude/brave-curie-wynhkp - draft PR AbdelrhmanBassiouny/cognitive_robot_abstract_machine#491

Plan: review follow-up for upstream cram2#696 (LucaKro, branch krrood_match_bug), based on
its head 32c4199 (mirrored as fork branch krrood_match_bug = PR base). User pushes it onto #696.

Done:
- Round 1: dropped PR's direct-children ConditionTruthRecorder; replace-child docstrings.
- Round 2 (user: "why _children_ at all"): StatementTruthRecorder observer records every
  condition the evaluation reaches (any depth, minus AND/OR, root always counts);
  SymbolicExpression._evaluate_in_new_context_ extracted from _evaluate_; coraplex message
  says "could not be satisfied". Replace-child: sibling duplicate fixed, CaseWhen elif ->
  replace all, every _replace_child_field_ compares _id_. Tests TDD; 1321 pass in test_eql.
- Round 3 (user: "why an observer?"): observer replaced by StatementTruths, which walks each
  root result's OperationResult.result_chain (pulled out of all_bindings) and classifies steps
  with the context's truth_value_operator_children via is_condition_participant.
  SatisfiedConditionTracker can't serve: only runs under a query where (None for bare
  conditions), skips false results. Quantifier internals are not in the chain -> the
  quantifier itself is the statement.
- Round 4 (user review, 5 threads): StatementTruths class removed -> evaluate_statements_of(condition)
  returns statement results; factories filter by is_true. is_condition_participant takes an
  explicit evaluation_context (no as_current). Commit 231cfb10cb. Replied on all 5 threads;
  resolved the is_condition_participant + "removed inheritance" threads; left open: AND/OR skip
  (x2, answered why, no change - removing breaks 6 of 12 tests) and query+where (answered no:
  zero results when no solution).
- Round 5 (2 threads): statements = condition itself + steps the context recorded as
  evaluated as a TVO operand (truth_value_operator_children); is_condition_participant no
  longer used (its by-type check reported comparisons passed as predicate values) and its
  evaluation_context param reverted; is_statement_of -> is_statement. New TDD test
  test_comparisons_a_statement_takes_as_values_are_not_statements_of_it. Commit 9d8667425c.
  Resolved the "participant takes context not condition" thread; left open "isn't reached
  enough?" (answered no with the chain dump).
- Round 6 (2 threads): is_statement inlined into evaluate_statements_of (context/chain/condition
  always from one evaluation) - commit bea1af44bf, thread resolved. Open, awaiting user:
  rename to is_atomic_condition_of? Not is kept (and its operand reported too), so "atomic" is
  wrong today. Options offered: skip Not (truly atomic; failed not_(a) reports nothing) or keep
  negation whole and drop Not's operand (recommended; "literals" but Literal clashes).

Next / open (ask user):
- coraplex ConditionNotSatisfied message is built at construction, i.e. at motion-chart build
  time before the motion runs -> needs a lazy message; touches coraplex + giskardpy
  CancelMotion (exception field, copied in motion_statechart.py:754). Separate PR off main.
- First two commits carry the old "Made with the help of Claude" line (AGENTS now forbids
  naming the service); amend/force-push was denied this session.
