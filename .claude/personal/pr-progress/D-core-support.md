**Plan**
- #67 stalled on a base_expressions.py conflict with D-core-serialization; merge it, keep the pre-installed-context fix, restack descendants.

**Done**
- Merged the base as ff9a89984 (probe clean at that commit); set the active conditions root in `_evaluate_within_`; both conditions-root tests fail without it and pass with it.
- Local runs at ff9a89984: test_eql_rdr 112 passed, test_eql 1442 passed / 3 skipped (typing-overload module excluded, no mypy).
- Restacked D-core-expert (conflicts resolved), single-class, backend and the D-ui/D-store/D-deco branches.

**Next**
- Read CI on #67 (none read after the push).
- claude/rdr-why-answer-6fnw2o conflicts in explanation.py and observer.py: its owner decides.
- #67 stays ready (the developer chose that); threads at rule_tree_view.py:255 and test_conclusion_domain.py are the developer's to resolve.
