**Plan**
- Make every EQL module import without random_events/probabilistic_model; probabilistic parts live in krrood.parametrization.

**Done**
- Resolve of 25049d9a99: causal_relation (new from main) moved to krrood.parametrization; it failed test_each_lib (krrood) at d27b63faeb. Import script with both libraries blocked exits 0 locally; CI not run on it yet.
- PR description updated to the current state.

**Next**
- CI on 25049d9a99 (pytest, ruff, docformatter, krrood check not runnable here).
- Upstream #985, changes requested by LucaKro: parametrization/__init__.py rule-registering import (author said they would look for another way; open design call), "wall of text" in probabilistic_backend.py (unclear which text; unanswered), weird names (author deferred to another PR).
