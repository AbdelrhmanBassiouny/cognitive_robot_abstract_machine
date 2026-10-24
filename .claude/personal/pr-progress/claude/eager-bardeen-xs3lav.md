PR #517 (draft; head claude/festive-pascal-g09gl3, same commit as this branch): dev tools in krrood.

Plan
- krrood.development_tools: `krrood format` (ruff+docformatter), `krrood agents-md` keeps a marked block of shared rules (per-section files, python/krrood sets, source comments), extra krrood[development-tools].

Done
- Pushed 93fe85dfd (marked block; AGENTS.project.md merged into AGENTS.md); 27 tool tests pass; --check passes with --no-deps install.

Next
- User/team review of #517, then promotion; CI on 517 not yet seen.
- basstler adoption waits for krrood-light-core item krrood-core-and-all-extras.
