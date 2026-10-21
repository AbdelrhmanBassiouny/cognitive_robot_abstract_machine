Branch claude/blissful-davinci-9fogks, PR #477 -> main (ready, marked by user); upstream PR open on cram2.

Plan:
- Bindings-based generation + ProbabilisticOperationResult scoring (landed on the branch).

Done:
- ec0af2b0f ProbabilisticModelException base (upstream review, relayed by user): all probabilistic_model
  exceptions + 11 krrood parametrization model exceptions. krrood 2732 passed, pm 1127 passed.
- f8ab5bc15 ValueOutsideVariableDomain; review thread 4326175838 replied, left open.

Next:
- This session cannot reach cram2 (same-named repo can't be attached next to the fork): upstream review
  replies must be posted by the user or a session with cram2 attached.
- Numeric pattern variable hash_map AttributeError (also on main): separate bug task.
Env: .venv; run per package with --confcutdir; restore test_verbalization/verbalization_results.py after runs;
ignore test_gui (no libEGL) and test_mesh_three_graph_visualizer (needs semantic_digital_twin).
