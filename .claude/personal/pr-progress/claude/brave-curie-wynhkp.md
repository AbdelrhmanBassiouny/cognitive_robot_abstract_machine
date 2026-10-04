## claude/brave-curie-wynhkp - draft PR AbdelrhmanBassiouny/cognitive_robot_abstract_machine#491

Plan: review follow-up for upstream cram2#696 (LucaKro, branch krrood_match_bug), based on
its head 32c4199 (mirrored as fork branch krrood_match_bug = PR base). User pushes it onto #696.

Done:
- Dropped ConditionTruthRecorder; get_true/false_statements read truths from the bindings of
  one plain _evaluate_(); callback replaced by private _statements_that_held_(statement, held).
- Documented _replace_child_ contract (all references in this parent; other parents keep it).
- Tests: 109 affected pass, 1314 in test_eql (env lacks probabilistic_model for 8 files).

Deliberately left out (follow-ups, ask user):
- Nested and_ reported as "AND"; lone predicate -> []; AND false-statement is order dependent.
- coraplex ConditionNotSatisfied builds its message at construction time (chart build), so
  get_false_statements runs before the motion for the motion-chart path.
- _replace_child_ can duplicate a sibling (f(x, y), x->y); mixed is/_id_ comparisons.
