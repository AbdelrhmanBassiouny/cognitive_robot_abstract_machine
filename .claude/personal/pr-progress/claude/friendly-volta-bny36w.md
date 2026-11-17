**Plan**
- Make every EQL module import without random_events/probabilistic_model; probabilistic parts live in krrood.parametrization.

**Done**
- 25049d9a99: causal_relation (new from main) moved to krrood.parametrization; it failed test_each_lib (krrood) at d27b63faeb.
- 9964645ff7: Distribution/Probability grammar rules moved into probabilistic_queries (no __init__ import); backend prose and comments trimmed. Import script with both libraries blocked exits 0 locally.
- PR description updated to the current state.

**Next**
- CI on 9964645ff7 (pytest, ruff, docformatter, krrood check not runnable here); doctest harness unchecked.
- Upstream #985: threads on the __init__ import and the wall of text are addressed, the names thread is deferred to another PR; the owner replies and resolves them.
