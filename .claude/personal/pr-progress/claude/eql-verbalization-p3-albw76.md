# PR #88 — P3: abstract→concrete-subclass expansion + first-order form

Status: pushed (4 commits), PR #88 marked **ready for review** by the developer (no longer draft) —
base still `claude/eql-verbalization-operand-naming-n0gb95` (P2), merges in P1 (#86) too. Subscribed
to activity. Review round 1 (3 comments) fully handled; review round 2 (1 comment, design question)
fixed and resolved too; review round 3 (1 comment, test quality) fixed and resolved too. Developer's
answer on the base/stacking question (round 1's general comment) is still pending, but marking it
ready-for-review may itself be the answer (proceeding with current stacking) -- not assumed, just
noted. CI green so far (16/18 checks passed, 2 still running, none failed) at last check. Hourly
check-in loop active.

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
- **Review round 1** (3 items, pushed dbc4444f):
  (a) `operand_head_noun`'s abstract-type label used a manual `" or ".join(...)` instead of
  reusing `disjunctive_type_head`'s Oxford-comma joining — a real latent bug (agreed with 2
  alternatives, would've silently diverged from the rendered fragment at 3+, e.g. "Drum or Flute
  or Harp" vs the real "Drum, Flute, or Harp"). Fixed to
  `flatten_fragment_to_plain_text(disjunctive_type_head(alternatives))`; added an
  `Instrument`/`Drum`/`Flute`/`Harp` three-member mimic family to lock it in. Replied and resolved.
  (b) Developer thought `surface_verification.py` was already in #87 — clarified it's entirely
  from #86 (P1), not #87; #87 never touches that file. Replied, not resolved (informational).
  (c) General review comment asked "did you rebase on #87 or no?" given the diff volume — replied
  explaining the base is correctly #87, the extra volume is #86 merged in on purpose (to reuse
  P1's already-built first-order mechanism rather than duplicate it), and offered two alternatives
  if this stacking is more confusing than it's worth: (i) wait for #86+#87 to land on `main` and
  rebase P3 there, or (ii) target `main` directly and call out the P1+P2 overlap in the
  description instead of via the base branch. Awaiting the developer's preference.
- **Review round 2** (1 item, pushed 19280e06): "Why does a first_order_form take overrides?" — a
  real design flaw, not just a question: a truly value-agnostic rendering needs nothing external,
  so `operand_overrides` had no business being on the general `placeholder_operands`/
  `first_order_form` signatures — it exists only because `SymbolicSurfaceSnapshot`'s committed
  example sentences need a real value for a field whose fragment reads it directly (e.g. `HasType`'s
  `types_`). Removed the parameter from both general functions; `SymbolicSurfaceSnapshot.
  placeholder_operands` now calls the override-free general function and layers its own
  registered overrides on top itself, keeping that concern local to the snapshot. Retargeted the
  two override tests at `SymbolicSurfaceSnapshot` directly instead of the free functions. Replied
  and resolved.
- **Review round 3** (1 item, pushed 68cea9fd): "I don't get it why 'ash' doesn't appear? didn't we
  override 'catalyst' to be 'ash'?" — a real test-quality gap, not a misunderstanding on the
  developer's part: `Kindled`'s fragment only ever read `fuel`, so the override test asserted the
  overridden and un-overridden renderings were *equal*, proving nothing. Gave `Kindled`'s fragment
  a second clause reading `catalyst` too ("an Igniter is lit with ..."), so the default now reads
  "a catalyst" (field-name fallback) and the override genuinely reads "with 'ash'" — visible in the
  string itself. Updated the affected assertions (and the value-using-form comparison test, which
  had bound `catalyst` to a raw `object()` whose repr would otherwise now leak into the sentence —
  swapped for an equivalent placeholder variable). Replied and resolved.

## Next
- Wait for the developer's answer on the base/stacking question (comment above) — be ready to
  either rebase onto `main` once #86/#87 merge, or re-target the PR base to `main` directly.
- Otherwise keep watching CI and any further review comments via the hourly check-in (webhooks
  don't cover CI success, new pushes, or merge-conflict transitions).
- If review pushes back on the shared-article ("a Body or Region") vs repeated-article
  ("a Body or a Region") choice, revisit `NounPhrase`'s single-head assumption.
- P4 (sdt = PR #33 rebase) still needs P1 + P2 + P3 all merged to main first.
