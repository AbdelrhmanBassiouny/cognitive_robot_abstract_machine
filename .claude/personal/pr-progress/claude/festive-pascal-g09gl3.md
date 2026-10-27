PR #517 (ready): krrood development tools; upstream cram2#806.

Plan
- Answer cram2#806 review: section names are broad topics; a topic may recur across rule sets, siblings never share a title.

Done
- 0193fdb98: project RunningTests folded into GeneratedORMInterfaces (duplicates tomsch420 flagged).
- 3aec5a7bf, 2e94103c4: krrood sections are Exceptions, ConstantsAndClassLevelValues, Enums, Serialization, Generics; test checks sibling titles only.

Next
- User replies on cram2#806 threads (krrood_rules.py:28/99, python_rules.py:443/511/563) and re-requests tomsch420.
- coraplex_garmi_demo check red upstream, unrelated to this diff.
- After merge: basstler PR replacing format_docstrings.py and AGENTS.md.
