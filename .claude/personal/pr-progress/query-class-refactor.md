## Plan
Land the EQL query-class refactor as PR #5 (base: match-where-without-resolve): spec/product
lifecycle, subquery result caching, and a composable result-transformer pipeline.

## Done
- Refactor complete; merged query-interface-refactor, role-pure-composition, match-where, main.
- Addressed all review rounds and replied on each thread: modifies_query_structure decorator
  (incl. distinct, built from _distinct_on directly), _result_stages_ /
  _aggregators_of_type_count_all_ renames, removed dead MatchVariable + import cleanup, inline
  comments (PEP-479 next() sentinel, cached_property __dict__.pop), spec -> specification, a/an,
  get_type_hints_of_object.
- Resolved the merge conflict against the advanced base: merged origin/match-where-without-resolve
  (from_() fix, create_variable simplification, main merge b2f520362) into query-class-refactor,
  took HEAD for all EQL refactor code, took base's from_()/None-guard in match.py, took base for the
  two generated files (sdt ormatic_interface.py, scrdr_expert_answers_fit.py). Full EQL suite green
  (1029 passed, 3 skipped). Pushed 6e7e59aeb; PR now mergeable (was dirty).
- Resolved the 4 completed review threads (MatchVariable, PEP-479 sentinel comment, __dict__ cache
  comment, distinct-decorator); left open the _root_query_ design Q&A and the _var_-as-Role
  follow-up thread.

## Next
- Watch PR #5 CI on the new merge commit (17 checks running); address any krrood failure.
- Merge once approved.
- Follow-up (separate PR, prompt already given): model Selectable._var_ as an explicit Role/delegate.
