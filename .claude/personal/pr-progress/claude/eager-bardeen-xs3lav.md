PR #517 (draft; head claude/festive-pascal-g09gl3, same commit as this branch): dev tools in krrood.

Plan
- krrood.development_tools: `krrood format`; `krrood agents-md` generates whole AGENTS.md (Jinja) from sections = `Section(AgentRule, Enum)` enums (members are rules), nested via a `NestedIn[Parent]` base before Section (plain Generic; SubClassSafeGeneric's ABC metaclass conflicts with Enum); rule sets = RuleSet subclasses; project sections imported via repo agent_rules.py.

Done
- Pushed 31e281677 (enum sections + NestedIn[parent] base); 32 tool tests pass, AGENTS.md unchanged.

Next
- CI on 31e281677 not yet seen; wait for further review.
