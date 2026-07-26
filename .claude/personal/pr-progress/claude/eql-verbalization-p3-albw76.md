# PR #88 — P3: abstract→concrete-subclass expansion + first-order form

Status (2026-07-26): pushed (15 commits total, ea595142 latest). Marked **ready for review by the
developer themselves** (not by me) after ea595142 — per personal convention I don't override their
own explicit un-drafting; the "convert back to draft after any push" rule applies only to my own
pushes going forward, so the next commit I push (if any) should re-draft it as usual. Base `main`
(#86/#87 both merged there). Subscribed to activity. 14 review
rounds total, all now reply-and-resolved except round 6 (reconciliation question, informational —
nothing to resolve). Both threads round 12 left open pending discussion are now closed: the
grammar-justification one the developer resolved themselves after reading the Apple/Banana
argument; the `additional_heads` design one they replied "Ok keep it, however I'd like to see how
this behaves on repeat mention" — which led straight to round 13 finding and fixing a real bug,
and round 14 adding the pronoun-path companion test (see below). Description rewritten twice so
far: once for the 2026-07-24 rebase, once for round 11's repeated-article redesign; no further
rewrite needed for rounds 12-14 (no further user-visible surface change, only internal
layering/bugfix/docstring/test wording). CI checked through e66bf4b5: `krrood`'s own job green;
a `coraplex` job failure (an `ormatic_interface.py` regeneration/`ruff format` internal error) and
the recurring pre-existing `semantic_digital_twin` flake (`test_world_sim_state_sync`) both
confirmed unrelated to this PR — neither touches any file this PR changes, and the `coraplex` one
is deliberately left alone per AGENTS.md's guidance never to hand-fix `ormatic_interface.py`. CI
for ea595142 not yet checked. Hourly check-in loop active; PR still not merged/closed, so
subscription continues.

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
- Round 13 closed out both threads round 12 had left open: the grammar-justification one was
  resolved by the developer directly; the `additional_heads` one asked to see repeat-mention
  behavior, which surfaced and fixed a real bug (`CoreferenceProcessor._reduced`/`_rebuilt`
  dropping `additional_heads` on a definite repeat mention — see the roadmap section above for the
  full account) plus a permanent regression test. Round 14 followed up with the pronoun-path
  companion test, plus two more docstring/AGENTS.md polish items. Pushed as ea595142. All rounds
  now reply-and-resolved except round 6 (informational, nothing to resolve).
- CI checked through e66bf4b5: `krrood`'s own job green; the `coraplex` ORM-regeneration failure
  and the pre-existing `semantic_digital_twin` flake are both confirmed unrelated (see round 14
  above) — do not attempt to fix either from this PR. CI for ea595142 not yet checked, do that
  next.
- `mergeable_state` reported "unstable" at the 33a8da5b check (not "clean") — re-verify at the next
  status check; GitHub's mergeable-state cache can lag a push, and the reconciliation investigation
  (round 6) found nothing actually outstanding against `main`.
- P4 (sdt = PR #33 rebase) still needs P1 + P2 + P3 all merged to main first.
