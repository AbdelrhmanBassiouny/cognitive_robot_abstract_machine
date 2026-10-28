PR #517 (ready): krrood development tools; upstream cram2#806.

Plan
- development_tools/agents: Section(AgentRule, Enum) members are rules; shipped_rules/ package, one module per top-level section; RuleModule finds defined sections, alphabetical.

Done
- 4fab6af70: agents subpackage, shipped_rules split, RuleModule discovery, Miscellaneous dissolved, agent_rules may be a package.
- ddf666cb9: agents package __init__ files emptied (review).

Next
- User replies on cram2#806 threads (krrood_rules.py:28/99, python_rules.py:443/511/563; now shipped_rules.py) and re-requests tomsch420.
- coraplex_garmi_demo check red upstream, unrelated to this diff.
- After merge: basstler PR replacing format_docstrings.py and AGENTS.md.
