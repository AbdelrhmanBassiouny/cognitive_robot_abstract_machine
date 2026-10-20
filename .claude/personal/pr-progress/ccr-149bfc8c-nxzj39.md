PR #520 (fork, draft, label bug): nested query evaluation gets its own context.

Plan
- Fix: a query evaluated during another evaluation joins the outer context.

Done
- 365d4f3d4: evaluate() starts its own context; test with rule tree in lazy domain.
- 9a4230055: reuse a context set before evaluating (fixes experiments confidence
  guard CI failure); rename to _create_new_context_and_evaluate_ (review); added
  test_evaluation_runs_in_the_context_set_before_it_starts. Review thread resolved.

Next
- Confirm experiments CI is green on 9a4230055 (could not run locally: sdt ORM needs ROS).
- After landing: remove contextvars workaround in HoleRulesBackend.concluded_kind (#511).
