PR #509 (draft, bug, base main): importing the symbol graph no longer loads matplotlib.

Plan
- Remove the unused RWXNode import from class_diagram.py; test that the symbol graph loads no optional dependency.

Done
- Fix + test (failed before, passes after); 1679 krrood tests pass.

Next
- Await CI/review. The open question to the user: EQL match/query_graph still load matplotlib eagerly via RWXNode -> GraphVisualizer.

