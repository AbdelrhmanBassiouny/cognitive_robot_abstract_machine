# EQL planning: roadmap

- A goal is an EQL condition and a planner is an EQL backend that answers it with plans. Design and concepts: https://claude.ai/code/artifact/559b21dc-0e6c-41ce-9843-b06cb69fe62e (the Readings tab maps readings to items).
- The planner lives in krrood.planning, stays domain-agnostic and imports no other workspace package. The core fits the light install; continuous and probabilistic parts go behind krrood[all].
- State is a valuation of fluents. A State overlay stores only changed fluents and is read through EQL's evaluation context; it never mutates live objects or the SymbolGraph.
- Effects are assignments (obj.attribute := value, optionally conditional); fluents nobody assigns persist. Derived facts are EQL rules or symbolic functions and never appear in effects.
- EQL gives the meaning; search runs on a compiled integer state, not on EQL per step. Native planner first, the unified-planning backend after it.
- The robot side is eql-planning-robots (#522); keep the API it builds on (State, ActionSchema, PlanningBackend) stable once it starts on Nov 16.
- Core by Nov 13; trajectory constraints and the Fast Downward comparison in January. AAMAS 2027 rebuttal Nov 20-24.
- A fluent is any EQL ground term (attribute, index, call, predicate or symbolic function applied to concrete arguments); EQL reads every one through the TermReader in its evaluation context, which krrood.planning's State implements, and EQL never imports the planner.
