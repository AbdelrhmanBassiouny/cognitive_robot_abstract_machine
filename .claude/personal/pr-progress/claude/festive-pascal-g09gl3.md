PR #517 (ready): krrood development tools; upstream cram2#806.

Plan
- Answer reviews: rules typed by rule set (PythonRule/KrroodRule/ProjectRule); sections are enums named <Topic>Rules, nested via parent.

Done
- d3257b81f: typed rules replace RuleSet/default_rule_set; sections renamed *Rules; rendering via CodeGenerator; fork threads on agent_instructions.py and shipped_rules.py:493 resolved.

Next
- User replies on cram2#806 threads (krrood_rules.py:28/99, python_rules.py:443/511/563; now shipped_rules.py) and re-requests tomsch420.
- coraplex_garmi_demo check red upstream, unrelated to this diff.
- After merge: basstler PR replacing format_docstrings.py and AGENTS.md.
