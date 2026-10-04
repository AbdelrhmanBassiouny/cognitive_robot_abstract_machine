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

Next / open (ask user):
- coraplex ConditionNotSatisfied message is built at construction, i.e. at motion-chart build
  time before the motion runs -> needs a lazy message; touches coraplex + giskardpy
  CancelMotion (exception field, copied in motion_statechart.py:754). Separate PR off main.
- First two commits carry the old "Made with the help of Claude" line (AGENTS now forbids
  naming the service); amend/force-push was denied this session.
