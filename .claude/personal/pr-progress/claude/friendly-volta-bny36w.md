**Plan**
- Make every EQL module import without random_events/probabilistic_model; probabilistic parts live in krrood.parametrization.

**Done**
- Moves, lazy grammar and causal_relation landed; main merged into the branch (f65ac70135), merge probe clean.
- Upstream #985 approved by LucaKro and tomsch420; no unresolved upstream threads.
- PR description updated to the current state.

**Next**
- CI on f65ac70135 (fork and upstream) is queued; pytest, ruff, docformatter and krrood check not runnable here.
- After CI is green the owner resolves the open rule-registry thread (test_grammar_registry.py).
