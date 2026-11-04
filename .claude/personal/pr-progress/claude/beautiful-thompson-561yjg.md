Plan:
- Memo keyed on #535's CallTerm: CallResults on EvaluationContext, shared with nested evaluations
- InstantiatedVariable reads procedure calls through it; constructor calls and iterator results are not reused
- Predicate.__bool__ read once per instance per evaluation
- Tests first: counted mimics in test/krrood_test/dataset, test_eql/test_call_results.py
Done:
- Bootstrapped draft PR #553 on #535; depends_on swapped and posted on #507
Next:
- Write failing tests, implement, run test_eql, update PR
