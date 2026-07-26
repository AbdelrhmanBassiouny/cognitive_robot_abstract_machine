# PR #88 — P3: abstract→concrete-subclass expansion + first-order form

Status (2026-07-26): pushed (13 commits total, a4a69b06 latest). Still **draft** (developer
converted it back themselves earlier; per personal convention never marked ready again without
being explicitly asked). Base `main` (#86/#87 both merged there). Subscribed to activity. 12 review
rounds total: 10 reply-and-resolved, 2 deliberately left open — round 6 (reconciliation question,
informational) and two threads of round 12 where the developer explicitly said "discuss with me"
(the `NounPhrase.additional_heads` design, and the grammatical justification for the repeated
article) — replied with full reasoning but did not resolve, awaiting their response. Description
rewritten twice so far: once for the 2026-07-24 rebase, once for round 11's repeated-article
redesign; no further rewrite needed for round 12 (no user-visible behaviour changed, only internal
layering + docstring wording). CI on the latest push (33a8da5b, before round 12's a4a69b06) was
green except the known pre-existing `test_world_sim_state_sync` flake in `semantic_digital_twin`
(confirmed unrelated — 1 of 861 tests, a physics-settling tolerance flake present on `main` too);
`krrood`'s own job passed. CI for a4a69b06 not yet checked. Hourly check-in loop active; PR still
not merged/closed, so subscription continues.

### 2026-07-24 rebase (see the roadmap section above for the full account)
`main` had ~5 days of substantial unrelated activity by the time this session resumed, including
P2's own continued review (a `Distinguisher` ABC refactor, `GrammarMetadata` moved to
`krrood.entity_query_language.verbalization.grammar_metadata`) and unrelated work that moved
`surface_verification.py` to `krrood.entity_query_language.testing.surface_verification`. Two CI
checks failed on the stale `GrammarMetadata` import path; fixed both occurrences, confirmed the
`Distinguisher` refactor doesn't overlap with P3's own changes (verified via a disposable
`git worktree` trial merge before touching the real branch), then merged `main` in for real (3
mechanical import-only conflicts), fixed `test_first_order_form.py`'s import of the moved
`surface_verification` module, and reran the full suite (2012 passed) before pushing.

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
- Round 12 (2 fixed-and-resolved: import layering via new `disjunctive_phrase()` in
  `coordination.py`, "representative referent" docstring consistency pass; 2 left open on purpose
  since the developer explicitly said "discuss with me" — the `NounPhrase.additional_heads`
  design question and the grammatical justification for the repeated article) pushed as a4a69b06.
  Genuinely waiting on the developer's response to those two before doing anything further with
  them — do not unilaterally refactor `NounPhrase` again without their reply.
- CI not yet checked for a4a69b06 (only checked through 33a8da5b, which was green except the known
  pre-existing `semantic_digital_twin` flake) — check next session.
- `mergeable_state` reported "unstable" at the 33a8da5b check (not "clean") — re-verify at the next
  status check; GitHub's mergeable-state cache can lag a push, and the reconciliation investigation
  (round 6) found nothing actually outstanding against `main`.
- P4 (sdt = PR #33 rebase) still needs P1 + P2 + P3 all merged to main first.
