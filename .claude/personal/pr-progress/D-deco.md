## Next
- Push, restore #77 to draft, update its description.
- CI has never run on this branch's current stack; every figure above is a
  local measurement.

# PR plan: D-deco — @rdr decorator (Wave 0, S2b)
Decorator half of the @rdr path, stacked on D-store (#80). Base: `D-store`.
PR: #77 (draft).


## Scope
- `rdr/decorator.py` — `rdr()` factory, `RDRWrapper`, `empty_rule_tree_source`,
  `function_bound_to_its_own_name`.
- `rdr/templates/rdr_empty.py.jinja` — the rule-tree section of a model file
  that has no rules yet.
- `test_rdr_decorator.py` (27 tests) + `function_decorated_at_import.py`, the
  module that applies `@rdr` at import time so importing it is the exercise.
- `doc/eql/{developer,user}/rdr_decorator.md`.
