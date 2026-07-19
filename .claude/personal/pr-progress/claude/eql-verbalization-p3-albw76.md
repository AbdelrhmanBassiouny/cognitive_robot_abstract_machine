# PR #88 — P3: abstract→concrete-subclass expansion + first-order form

Status: pushed, draft PR #88 open, base `claude/eql-verbalization-operand-naming-n0gb95` (P2),
merges in P1 (#86) too. Subscribed to activity. CI just started (all jobs in_progress at last
check), no review comments yet.

## What's done
- Merged P1 into the P3 branch (one conflict, in `verbalization_surfaces.py`'s import block —
  resolved by keeping P2's `_example_domain` rename and dropping the now-unused `SymbolicCallable`
  import P1's version of the file no longer needed).
- `referring.py`: `_concrete_type_alternatives`/`operand_type_alternatives`/`disjunctive_type_head`
  + threaded `type_alternatives` through `_HeadNounGrouping`/`ReferringExpressions`/`NounForm`.
- `rules.py`: `VariableRule.build` renders the compound disjunctive head when present.
- `surface_verification.py`: extracted `placeholder_operands`/`first_order_form` as standalone
  functions; `SymbolicSurfaceSnapshot` delegates to them.
- Tests: `test_operand_referring.py` additions (mimics + unit + end-to-end), new
  `test_first_order_form.py`.
- Full suite verified green locally (venv312 in scratchpad), black+docformatter applied, PR opened
  as draft with description explaining the P1-merge and the shared-article divergence.

## Next
- Wait for CI on #88 and any review comments; re-check in about an hour via a scheduled
  check-in (webhooks don't cover CI success or new pushes).
- If review pushes back on the shared-article ("a Body or Region") vs repeated-article
  ("a Body or a Region") choice, revisit `NounPhrase`'s single-head assumption.
- P4 (sdt = PR #33 rebase) still needs P1 + P2 + P3 all merged to main first.
