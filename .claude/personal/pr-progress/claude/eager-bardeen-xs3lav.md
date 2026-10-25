PR #517 (draft; head claude/festive-pascal-g09gl3, same commit as this branch): dev tools in krrood.

Plan
- krrood.development_tools: `krrood format`; `krrood agents-md` generates whole AGENTS.md (Jinja) from sections = `Section(AgentRule, Enum)` enums (members are rules), nested via `class X(Subsection[Parent])` (Subsection is a Section; Section subclasses new pattern krrood.patterns.generic_enumeration.GenericEnumeration, whose metaclass sends str keys to member lookup, others to Generic); rule sets = RuleSet subclasses; project sections imported via repo agent_rules.py.

Done
- Pushed (after 0225c9f1e) InvalidEnumerationKey(KeyError, TypeError) for non-name keys on non-generic enums; 46 tests pass, AGENTS.md regenerated.

Next
- CI on latest head not yet seen; wait for further review.
