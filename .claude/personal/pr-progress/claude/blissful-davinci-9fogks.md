Branch claude/blissful-davinci-9fogks, PR #477 -> main (ready, marked by user); upstream PR cram2#777 open.

Plan:
- Bindings-based generation + ProbabilisticOperationResult scoring (landed on the branch).

Done:
- f15c328ae davidprueser's two cram2#777 threads: ProbabilisticOperationResult is Role[OperationResult]
  in base_expressions; Match._find_assigned_variable_ + NoAttributeWithAccessPathName replace
  test/krrood_test/pattern_variables.py. main merged to 4eaae933a. krrood 2765 passed (4 env fails), pm 1304 passed.

Next:
- Upstream thread replies on cram2#777 must be posted by the user or a session with cram2 attached.
- Fork thread r4326175838 (_stated_values_ as iterator) open, awaiting user's decision.
- Numeric pattern variable hash_map AttributeError (also on main): separate bug task.
Env: .venv (py3.12); run per package with --confcutdir; restore test_verbalization/verbalization_results.py after runs;
ignore test_gui (no libEGL), test_mesh_three_graph_visualizer, test_quantifier_overload_types (mypy);
graphviz and test_jacobian_dot/ddot fail pre-existing.
