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

- PR #4's latest comment (rename create_variable -> create_or_update_variable) was already handled
  by the owner directly (commit eac372c09) on match-where-without-resolve; nothing to do there.
  Propagated the same rename into PR #5 (query-class-refactor) as a pure rename (body was already
  byte-identical to the base's create_or_update_variable via the a8bfb09ce merge); match+queries
  tests green (104 passed). Pushed 96e82d448.

- Base advanced to f55221a12 (its rename eac372c09 + a merge), which re-conflicted PR #5 (dirty).
  Re-merged origin/match-where-without-resolve into query-class-refactor; only factories.py
  conflicted (docstring line-wrap, both referencing create_or_update_variable) - took base wrap.
  match tests green (23 passed). Pushed 695b0278b; PR #5 mergeable again (unstable = CI running),
  base now f55221a12.

- Owner restacked query-class-refactor onto main (375abd03c) and advanced match-where to 1a140d8c5
  (moved _resolve_domain into core/helpers.py). Fast-forwarded both local branches to origin.

- New review round from tomsch420 + davidprueser (both requested changes, ~12 comments, mostly
  docstring-formatting nits). Fixed on 9b6119efe: reformatted docstrings to the multi-line
  convention (evaluation_context OutermostQueryClaim/SubqueryResultCache + fields, eql_interface
  quantifier_type field+property with :return:); dropped redundant ellipsis in ResultTransformer;
  made Quantification.owner default consistent (bare = None) + removed unused field import; moved
  _STREAM_EXHAUSTED module global into CachedResultStream as a ClassVar; added while-True comment.
  Kept Ordering/Quantification names (pipeline stages, not old OrderBy node). Verified fixed-point
  of format_docstrings.py so pre-commit won't re-modify. Targeted tests 136 passed. Pushed.

- Owner follow-up on query.py:111 ("why not define the sentinel inside __iter__?"): moved
  _STREAM_EXHAUSTED from ClassVar to a local `stream_exhausted = object()` in __iter__, removed the
  ClassVar import. Subquery-caching tests 6 passed. Pushed cecdc5493; replied + resolved the thread.

## Next
- GitHub API still not surfacing the tomsch420 + davidprueser threads (AbdelrhmanBassiouny-authored
  ones do appear) - reply/resolve those once available. Reasoning to post: Ordering rename = pipeline
  stage vs removed tree node; while-True needed so exhausted stream still replays buffer.
- Watch PR #5 CI on cecdc5493; address any failure.
- Merge once approved.
- Follow-up (separate PR, prompt already given): model Selectable._var_ as an explicit Role/delegate.
