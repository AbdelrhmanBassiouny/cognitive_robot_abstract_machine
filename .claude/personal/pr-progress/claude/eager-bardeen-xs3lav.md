PR #517 (draft; head claude/festive-pascal-g09gl3, same commit as this branch): dev tools moved into krrood.

Plan
- krrood.development_tools: `krrood format` (ruff+docformatter), `krrood agents-md --rule-sets`, rules per section in python/krrood sets, extra krrood[development-tools].

Done
- Pushed 6bcfe183e to both branches; fork main merged; 23 tool tests pass; agents-md --check passes with --no-deps install.

Next
- User reviews #517, then promotes; CI on 517 not yet seen.
- basstler adoption waits for krrood-light-core item krrood-core-and-all-extras.
