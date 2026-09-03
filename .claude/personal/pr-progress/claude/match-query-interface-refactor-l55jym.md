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
