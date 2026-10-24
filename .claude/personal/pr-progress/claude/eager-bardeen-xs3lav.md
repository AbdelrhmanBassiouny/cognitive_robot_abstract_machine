PR #517 (draft; head claude/festive-pascal-g09gl3, same commit as this branch): dev tools in krrood.

Plan
- krrood.development_tools: `krrood format`; `krrood agents-md` generates whole AGENTS.md (Jinja) from sections = `Section(AgentRule, Enum)` enums (members are rules), nested via `parent` classproperty; rule sets = RuleSet subclasses (RuleSet.available); project sections imported via repo agent_rules.py.

Done
- Pushed 5bdb9da78 (enum sections + parent nesting); all review threads resolved; 31 tool tests pass, AGENTS.md unchanged.

Next
- CI on 5bdb9da78 not yet seen; wait for further review.
