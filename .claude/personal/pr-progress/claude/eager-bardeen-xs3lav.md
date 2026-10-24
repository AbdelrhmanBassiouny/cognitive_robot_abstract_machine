PR #517 (draft; head claude/festive-pascal-g09gl3, same commit as this branch): dev tools in krrood.

Plan
- krrood.development_tools: `krrood format`; `krrood agents-md` generates whole AGENTS.md (Jinja) from Section classes holding AgentRule attributes; RuleSet roots PythonRules/KrroodRules/ProjectRules (project = ProjectRules subclasses imported via repo agent_rules.py).

Done
- Pushed a4c4f0c58: titles derived from class names (sentence case, acronyms kept), SectionWithoutTitle removed; 30 tool tests pass.

Next
- Await user on r4368270223 (subsections) + r4368285294 (Enum): proposed `class Section(AgentRule, Enum)` with members as str/(statement, details) and nesting via `parent` classproperty (Generic on Enum impossible: subscripting = member lookup). Implement on "go".
- CI on a4c4f0c58 not yet seen.
