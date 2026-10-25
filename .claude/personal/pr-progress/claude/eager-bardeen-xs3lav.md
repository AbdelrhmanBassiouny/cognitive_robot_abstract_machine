PR #517 (draft; head claude/festive-pascal-g09gl3, same commit as this branch): dev tools in krrood.

Plan
- krrood.development_tools: `krrood format`; `krrood agents-md` generates whole AGENTS.md (Jinja) from sections = `Section(AgentRule, Enum)` enums (members are rules), nested via `class X(Subsection[Parent])` (Subsection is a Section; SectionType metaclass routes type keys to Generic; plain Generic; SubClassSafeGeneric's ABC metaclass conflicts with Enum); rule sets = RuleSet subclasses; project sections imported via repo agent_rules.py.

Done
- Pushed 63e70d374 (Subsection[parent]); 33 tool tests pass, AGENTS.md unchanged.

Next
- CI on 63e70d374 not yet seen; wait for further review.
