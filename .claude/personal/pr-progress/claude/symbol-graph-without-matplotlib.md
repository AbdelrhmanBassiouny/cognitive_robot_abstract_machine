PR #509 (draft, bug, base main): importing the symbol graph no longer loads matplotlib.

Plan
- Remove the unused RWXNode import from class_diagram.py; test that the symbol graph loads no optional dependency.

Done
- Fix + test (failed before, passes after); 1679 krrood tests pass.
- Review: probe module replaced by `python -X importtime` inside the test (1975b4c337); thread answered and resolved.

Next
- Await CI/review. EQL match/query_graph matplotlib is plan item matplotlib-optional (#510).

