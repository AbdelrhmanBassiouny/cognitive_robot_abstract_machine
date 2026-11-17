**Plan**
- Make every EQL module import without random_events/probabilistic_model; probabilistic parts live in krrood.parametrization.

**Done**
- 25049d9a99: causal_relation (new from main) moved to krrood.parametrization; it failed test_each_lib (krrood) at d27b63faeb.
- 9964645ff7: backend prose and comments trimmed (upstream wall-of-text thread). a8aaefe125: rules-in-queries attempt reverted, the __init__ import stays (user's choice).
- PR description updated to the current state.

**Next**
- CI on a8aaefe125 (pytest, ruff, docformatter, krrood check not runnable here).
- Upstream #985: the __init__ thread stays open by the user's choice, the wall-of-text thread is addressed, names are deferred to another PR; the owner replies and resolves them.
