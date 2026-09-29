## PR #192 — match-underscore-rename-and-forwarding (+ folded item 3)

Branch `claude/match-query-interface-refactor-l55jym`, draft PR #192, off `main`.
Carries #254 (`claude/match-query-ergonomics-kpemmp`, draft, `bug`), which this
session opened off `main` and merged in.

### Done in this session (2026-09-03)

1. **Merged `main`** (eighth conflict, cram2#590's `_prefix_for_part` extraction)
   and migrated its three new readers of renamed names — §6's silent-miss guard
   catching something for the first time since the properties came out.
2. **Review round 2**: the six `CausesEffect` construction tests read the match
   (`arm` -> `pick`); the three `match.resolve()` calls in the match-verbalization
   tests are gone; `part.variable` in `test_markov_chain.py` answered with a
   measurement.
3. **#254 + the last detour**: `Query._type_` was `None` for every query, so every
   chain built on one carried no type. Fixed on `main` in its own PR, merged in,
   and the six `_variable_` bindings in `test_random_events_translator.py` removed
   with every expected variable name unchanged.

`test/krrood_test`: 1930 passed, 5 skipped (1903 on #254 alone).

### Open, waiting on the developer

- **`.resolve()` in the feature-extraction tests** stays — load-bearing. Whether
  `ground()` should resolve its own argument is a `probabilistic_model` call.
- Unifying `_get_expression_` with `_symbolic_expression_`; whether
  `AttributeMatch._symbolic_expression_` should exist at all.
- **Landing hazard**: #159 still reads `match.matches_with_variables` and
  `match.variable`, so its cascade breaks when the two meet.

### Next

Nothing to push. Both PRs are drafts; CI queued. Per the personal notes this
session's obligation ends here — the open threads are the developer's to answer.

### Upstream review round on cram2#662 (2026-09-29, roadmap §36)

LucaKro and tomsch420 requested changes on cram2#662, with five threads; the
developer answered them on 2026-09-29. Four threads were addressed in `9d30cdf85`
(thread 3 by trimming the docstring, thread 4 by the spelling fix):

1. `variable_rooted` (query.py, LucaKro): it is now the `_variable_rooted_`
   property of every `SymbolicExpression`. `MappedVariable` asks its chain root
   to re-root it, and only `Query` does anything.
2. `_as_operand_` open/closed (tomsch420): measured first. Deleting the
   `SymbolicExpression` branch fails 391 tests, because every `Comparator`
   becomes a `Literal`. Both kinds now implement the new `Operand` interface
   (`_symbolic_expression_`), and only a plain value is a `Literal`.
3. `Match` class docstring: cut back to one paragraph.
4. `a(Adder)` -> `an(Adder)` in the docstring and in the exception suggestion.
5. `assigned_variable` wall of text (tomsch420): the new `MatchAssignedValue`
   interface (`_as_assigned_variable_`). `Cause`/`Confounder` share
   `CausalRoleMarker`, which makes the typed per-attribute copy, and the comment
   is gone.

`test/krrood_test` 2067 passed, 5 skipped, plus the two usual Graphviz failures.
`probabilistic_model_test` 656 passed; its GUI tests need `libEGL`.

### Open

- Upstream threads must be replied to and resolved **by the developer**:
  AGENTS.md forbids a session from commenting upstream.
- Fork CI on the three earlier heads sat at `action_required`, waiting for
  approval, so this push's CI may need approval too.
- Earlier open questions are unchanged (`ground()` resolving its argument, #159
  landing hazard). `_get_expression_` and `_symbolic_expression_` are still two
  names, now on two different interfaces (`HasExpression`, `Operand`).
### Fork review, 2026-09-29 (one thread, `factory_and_kwargs.py:53`)

"Shouldn't that be an error?" on `construct_instance` silently dropping a
keyword that names no factory parameter (added on `main` in e41583f2c). Done in
`f96201975`: it raises `KeywordNamesNoFactoryParameter`, unless the host's
`_is_kept_out_of_construction_(value)` hook says otherwise. `Match` says so for
a `CausalRoleMarker`, because a marked keyword that is not a field names an
aggregation statistic (`chair_count=cause`). With the drop made to raise, only
that one test failed. Replied and resolved. `test/krrood_test` 2071 passed.
