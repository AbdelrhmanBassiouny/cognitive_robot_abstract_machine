PR #517 (draft; head claude/festive-pascal-g09gl3, same commit as this branch; base claude/generic-enumeration = PR #530): dev tools in krrood.

Plan
- krrood.development_tools: `krrood format`; `krrood agents-md` generates whole AGENTS.md (Jinja) from sections = `Section(AgentRule, GenericEnumeration)` enums (members are rules), nested via `class X(Subsection[Parent])`; rule sets = RuleSet subclasses; project sections via repo agent_rules.py.
- PR #530 (draft, claude/generic-enumeration off main): krrood.patterns.generic_enumeration.GenericEnumeration + InvalidEnumerationKey(KeyError, TypeError) + tests. #517 merges that branch; retarget #517 to main once #530 lands.

Done
- Split the pattern into #530 (ce1461a61); #517 at d8a67595c (merge of it, no content change); 46 tests pass.

Next
- CI on both not yet seen; wait for review.
