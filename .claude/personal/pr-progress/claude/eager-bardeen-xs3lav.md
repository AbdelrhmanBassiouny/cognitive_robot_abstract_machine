PR #517 (draft; head claude/festive-pascal-g09gl3, same commit as this branch): dev tools in krrood.

Plan
- krrood.development_tools: `krrood format`; `krrood agents-md` renders a marked block (Jinja) from Section subclasses + catalogues (enum per rule set x section: PythonRules/KrroodRules shared, ProjectRules subclasses in repo agent_rules.py).

Done
- Pushed 1b6d7aefd (sections as classes, CodeReference, template, subclass registration, markers renamed); 8 of 9 new threads resolved; 42 tool tests pass.

Next
- Open thread r4367788807: user to confirm full-deps agents-md (no-deps CI job dropped; check now in krrood job) vs text references.
- CI on 1b6d7aefd not yet seen; basstler adoption waits for krrood-core-and-all-extras.
