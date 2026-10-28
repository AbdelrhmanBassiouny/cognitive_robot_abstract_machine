PR #517 (ready): krrood development tools; upstream cram2#806.

Plan
- Sections are enums named <Topic>Rules mixing in AgentRule; members are the rules; no rule sets; nesting via parent.

Done
- 138046f71: Section(AgentRule, Enum); --rule-sets and Python/Krrood/ProjectRule removed; AgentsInstructions(root, sections) + from_repository.

Next
- User replies on cram2#806 threads (krrood_rules.py:28/99, python_rules.py:443/511/563; now shipped_rules.py) and re-requests tomsch420.
- coraplex_garmi_demo check red upstream, unrelated to this diff.
- After merge: basstler PR replacing format_docstrings.py and AGENTS.md.
