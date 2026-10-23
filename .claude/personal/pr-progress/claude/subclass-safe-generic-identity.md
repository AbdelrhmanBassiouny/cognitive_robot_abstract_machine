PR #528 (draft, bug, base main): SubClassSafeGeneric is @dataclass(eq=False), so eq=False subclasses keep identity and stay hashable. Plan: domain-models, item subclass-safe-generic-identity.

Plan
- One root cause: the generated __eq__/__hash__=None of a fieldless dataclass base.

Done
- Pushed 0d03858949; 2 new tests fail before, pass after; krrood 2754 pass (2 object_diagram failures also on main). Merged into #527.

Next
- Read CI. Promote before #527.
