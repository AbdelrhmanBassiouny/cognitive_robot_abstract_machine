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

### Outcome: superseded by a tracked plan
The investigation is now the **`eql-existential-semantics`** plan (tracking issue #137,
dashboard <https://claude.ai/code/artifact/b2971b63-c5b5-466d-8542-6f5008f303cf>) — 8
items, 4 waves, 5 tracks, all findings/literature/TDD cases recorded in its `plan.yaml`
and `roadmap.md` on the personal-notes branch. This branch itself carries no code and is
not an item in the plan; new work starts on the plan's own item branches.

Key reversal recorded there: the binding-order fix is the **prerequisite**, not an
optional extra — a correct semi-join `exists` evaluated without a bound outer relation
returns *every* row. Wave 1 is blocked on PR #99 (`rdr-refactor`) merging.

User decisions (2026-08-03): block on #99; OR/safe-range as its own parallel track; hard
API break with no shim; tracking issue yes.
