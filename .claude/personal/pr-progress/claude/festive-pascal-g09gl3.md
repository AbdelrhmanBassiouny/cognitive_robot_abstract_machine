PR #517 (ready): krrood development tools; upstream cram2#806.

Plan
- Answer cram2#806 review: one section per topic; rule sets are tags on rules (default per top-level section).

Done
- 0193fdb98: project RunningTests folded into GeneratedORMInterfaces (duplicates tomsch420 flagged).
- 995d72074: rule sets became tags; topics declared once in shipped_rules.py (krrood rules merged in); fork thread on doc:121 resolved.

Next
- User replies on cram2#806 threads (krrood_rules.py:28/99, python_rules.py:443/511/563; files now merged into shipped_rules.py) and re-requests tomsch420.
- coraplex_garmi_demo check red upstream, unrelated to this diff.
- After merge: basstler PR replacing format_docstrings.py and AGENTS.md.
