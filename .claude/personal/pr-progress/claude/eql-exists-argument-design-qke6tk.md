## `exists()` first-argument design (branch `claude/eql-exists-argument-design-qke6tk`)

Status: **investigation / discussion only, no code written, no PR yet.** User asked whether
`exists(variable, condition)` needs the variable at all, and to discuss before doing anything.

### What was done
Read `Exists` (`operators/logical_quantifiers.py`), its factory, and every consumer
(`ExistsRule` + `QuantifierScope` in verbalization, `_translate_exists` in
`ormatic/eql_interface.py`, `query_graph._propagate_faded_subtrees`, `ForAll._invert_`).
Then ran empirical probes (scratchpad `probe_exists{,2,3,4}.py`, env: `pip install
./random_events` + typing_extensions/ordered_set/rustworkx/casadi/scipy/pandas/inflect/
lemminflect/pyjpt, `PYTHONPATH=krrood/src:probabilistic_model/src`).

### Findings (all reproduced)
1. Every one of the 5 real call sites already mentions the first argument inside the
   condition — the argument carries zero information today.
2. `Exists(cond, cond)` and a condition-only subclass both give the *correct* answer.
3. `exists(unrelated_var, cond)` silently returns wrong rows; `exists(empty_var, cond)`
   silently returns nothing; `exists(selected_var, cond)` returns everything.
4. Propagation reads `val.bindings` (the variable's), not `cond_val.bindings`, so an outer
   selected variable bound only inside the condition is dropped → cross product.
5. Independent real bug: the `return` after the first witness is global, so
   `an(entity(box).where(exists(fruit, HasType(fruit, Apple))))` returns only the *first*
   matching box. Binding the outer variable with a preceding condition masks it.
   `not_(exists(...))` and `for_all(...)` alone are broken the same way.

### Proposal put to the user
`exists(*conditions)` with semi-join semantics: local = free(condition) \ outer-visible;
one row per distinct outer binding, first witness per group, locals never escape. Keep
`for_all`'s variable (the ∀/∃ split is not derivable). Awaiting the user's decision on
scope (API change alone, or the short-circuit fix too, and whether they are one PR or two).
