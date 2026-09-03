## PR #192 — match-underscore-rename-and-forwarding (+ folded item 3)

Plan item `match-underscore-rename-and-forwarding` of `match-query-ergonomics`
(tracking issue #181). Branch `claude/match-query-interface-refactor-l55jym`,
draft PR #192, based on `main`.

### This session (2026-09-03, second round) — done

- **Merged `main` (eighth conflict).** cram2#590 extracted the part-prefix
  logic out of `rspn.py` into `RelationalDistributionTemplate._prefix_for_part`
  over the lines this branch had renamed — one hunk, main's extraction kept,
  the helper reads `_variable_`.
- **§6's silent-miss guard caught main's new readers**, the first arrival since
  the compatibility properties came out: `room_query.kwargs["objects"]` and
  three `f"{part.variable}.type"` sites in `test_markov_chain.py`, plus
  `str(part.variable)` in `template.py`. All migrated.
- **Review round, three of four threads acted on.** The six `CausesEffect`
  construction tests read the match directly (binding renamed `arm` -> `pick`);
  the three `match.resolve()` calls in the match-verbalization tests are gone.
- Full `test/krrood_test`: 1925 passed, 5 skipped. Pushed as 49c139b28 (merge)
  and 894b2142c (review round).

### Open, waiting on the developer

- **`Query._type_` is `None`**, so a chain built on a query carries no type and
  the random-events translator raises on a match-rooted one. Pre-existing on
  `main`. The four `translate(...)` sites in `test_random_events_translator.py`
  therefore keep `_variable_`; thread left open with the measurement.
- **`.resolve()` in the feature-extraction tests stays** — load-bearing, and
  making `ground()` resolve its own argument is a `probabilistic_model` change
  the developer should choose. Thread left open.
- Two older questions still on the PR: unifying `_get_expression_` with
  `_symbolic_expression_`, and whether `AttributeMatch._symbolic_expression_`
  should exist at all.
- **Landing hazard**: #159 still reads `match.matches_with_variables` and
  `match.variable`, so its cascade breaks when the two meet.

### Next

Nothing to push. The PR is a draft, mergeable, CI re-running on 894b2142c.
Per the personal notes, this session's obligation ends here — the open threads
are the developer's to answer.
