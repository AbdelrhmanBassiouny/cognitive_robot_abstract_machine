Branch claude/blissful-davinci-9fogks, draft PR #477 -> main (#192 landed).

Plan:
- Bindings-based generation + ProbabilisticOperationResult scoring (all landed on the branch).

Done:
- f8ab5bc15 ValueOutsideVariableDomain for out-of-domain bindings (object, its feature, non-member symbolic value).
- 5c82c373d merged main c50387cf7. krrood 2333 passed, pm 1076 passed (2 graphviz-dot env failures).
- Replied on review thread 4326175838 (_stated_values_ iterator, main's code); left open for the user.

- Promotion link built (head f8ab5bc15, clean on cram2 main c50387cf7), recorded under "## Promote", label promotion-link-sent:
  https://github.com/cram2/cognitive_robot_abstract_machine/compare/main...AbdelrhmanBassiouny:cognitive_robot_abstract_machine:claude/blissful-davinci-9fogks?expand=1

Next:
- User clicks Create on the promotion link once CI is green; await user on the _stated_values_ thread.
- Numeric pattern variable (variable(float, [...])) AttributeError hash_map is on main too: suggested as separate bug task.
Env: .venv (uv>=0.9); casadi~=3.7.0 installed by hand; run krrood with --confcutdir (no --orm-build there);
restore test_verbalization/verbalization_results.py before committing.
