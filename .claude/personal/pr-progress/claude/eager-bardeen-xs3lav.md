PR #517 (draft; head claude/festive-pascal-g09gl3, same commit as this branch): dev tools in krrood.

Plan
- krrood.development_tools: `krrood format` (ruff+docformatter); `krrood agents-md` generates a marked block from rule catalogues: PythonRules/KrroodRules (shared) + ProjectRule catalogues in the repo's agent_rules.py (CRAM: CramRules/CramSection).

Done
- Pushed 0f839cbef (project rules in code); all #517 review threads resolved; 40 tool tests pass; --no-deps check passes.

Next
- User/team review of #517, then promotion; CI on 0f839cbef not yet seen.
- basstler adoption waits for krrood-light-core item krrood-core-and-all-extras.
