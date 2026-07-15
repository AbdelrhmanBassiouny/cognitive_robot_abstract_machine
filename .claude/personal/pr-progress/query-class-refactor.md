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
- CI green; PR marked ready-for-review by the owner.

## Next
- Keep watching PR #5 (subscribed) for new review comments / CI failures; address as they land.
- Merge once approved.
- Follow-up (separate PR, prompt already given): model Selectable._var_ as an explicit Role/delegate.
