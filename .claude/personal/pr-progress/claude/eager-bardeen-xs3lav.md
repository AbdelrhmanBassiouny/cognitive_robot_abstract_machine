PR #517 (draft; head claude/festive-pascal-g09gl3, same commit as this branch): dev tools in krrood.

Plan
- krrood.development_tools: `krrood format`; `krrood agents-md` generates whole AGENTS.md (Jinja) from Section classes holding AgentRule attributes; RuleSet roots PythonRules/KrroodRules/ProjectRules (project = ProjectRules subclasses imported via repo agent_rules.py).

Done
- Pushed 1632e51cf (sections hold rules, RuleSet enum + markers removed, Misc->Miscellaneous); 30 tool tests pass; 6 of 8 new threads resolved.

Next
- Open: r4368111586 (keep AgentRule vs bare str for detail-less rules); r4368156346 (entry module: keep agent_rules.py convention vs pyproject setting).
- Krrood rules now a separate top-level part (offered to re-interleave if user objects). CI on 1632e51cf not yet seen.
