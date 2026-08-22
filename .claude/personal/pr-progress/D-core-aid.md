# D-core-aid (#63) — resolve rounds, 2026-08-22

## Round 1
- #161 widened to finish the two renames it had missed; #63 narrowed to `aid.py`;
  #189 opened for the flaky skip; 4 threads answered; manifest/roadmap §23/dashboard/#94.

## Round 2 (follow-up review)
- CI was red on `test_each_lib (semantic_digital_twin)` — `test_world_sim_state_sync`,
  which #63's 49 krrood lines cannot reach. Branch was **10 commits behind main** and
  predated `a7c21ffe6`'s flaky marking. Merged main into #63 (`8c041a10`) and #161
  (`d0df7534`).

## Round 3 (the reversal, and the plan gap)
Developer: *"do it here, and I am wondering why isn't #161 existing in any plan? fix that."*

- **`test_condition_resolver.py` moved back to #63 whole** (`c21e1fe3`) — dividers,
  corrected header names, the 3 `test_target_knowledge_resolver_*` names, module docstring,
  `materialized_guard` wording. #161 dropped its copy (`79a2dfb2`) and keeps only
  `backward_inference.py` + `condition_resolver.py` docstrings and
  `test_backward_inference.py`'s test name. **No file touched by both** — `git merge-tree`
  confirms #161 merges into `D-core-aid` clean.
- **#161 and #189 added to `plan.yaml`** as `S0-steward` items
  (`backward-inference-rename-completion`, `mcrdr-stop-only-flaky-skip`), precedent #89.
  Roadmap §24, dashboard republished (47 items, 0 drift), #94 comment `5380042352`.
- Thread replied + resolved. Both PR bodies rewritten.

Verified each push: `test_eql_rdr` 45 passed / 0 failed, collected-id diff exactly the 3
renames; `test_eql` 1179 passed / 3 skipped / 0 failed.

## Outstanding (developer's)
- **`@pytest.mark.flaky` looks inert**: appears once in the repo, unregistered in
  `pytest.ini`, no rerun plugin declared, CI runs bare `pytest -n auto` with no `--reruns`.
  Needs the plugin + marker registration + `--reruns N` to do anything. Bears on #189,
  which uses `@unittest.skip` (disables coverage) where the marker would keep it.
- **#189** was marked ready by the developer, so this session's job on it ended. Its open
  question stands: the test passed 18/18 across 4 configurations.
- 2 rename threads on #63 still open (the `_materialize` and `TargetKnowledgeResolver`
  ones) — both now actually done here, so they are closable.
- Dashboard's `D-ui-rendering` deferred-dependency drift rule exists in published output
  but not in `build_dashboard.py` on main.

## Next
Nothing for this session. CI in flight on #63 and #161; no check-in armed.
