PR #517 (draft; head claude/festive-pascal-g09gl3, same commit as this branch): dev tools in krrood.

Plan
- krrood.development_tools: `krrood format` (ruff+docformatter), `krrood agents-md` keeps a marked block of shared rules; rules are AgentRule (PythonRule/KrroodRule) members of PythonRules/KrroodRules enums; block auto-added when no markers.

Done
- Pushed ee3285b3d (rules in code, auto-adopt); 33 tool tests pass; --check passes with --no-deps install.

Next
- Open thread: user decides whether ProjectRule (generated project rules) replaces hand-written ones.
- User/team review of #517, then promotion; CI on ee3285b3d not yet seen.
- basstler adoption waits for krrood-light-core item krrood-core-and-all-extras.
