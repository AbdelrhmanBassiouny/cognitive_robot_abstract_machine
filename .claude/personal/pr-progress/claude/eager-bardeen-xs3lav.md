PR #517 (draft; head claude/festive-pascal-g09gl3, same commit as this branch): dev tools in krrood.

Plan
- krrood.development_tools: `krrood format`; `krrood agents-md` generates whole AGENTS.md (Jinja) from Section classes (rules = AgentRule class attributes, subclass = subsection; not Enum since enums with members can't be subclassed); rule sets = RuleSet subclasses; project sections imported via repo agent_rules.py.

Done
- Pushed 265eb20f5 (reverted enum/parent design back to subclass nesting); 30 tool tests pass, AGENTS.md unchanged.

Next
- CI on 265eb20f5 not yet seen; wait for further review.
