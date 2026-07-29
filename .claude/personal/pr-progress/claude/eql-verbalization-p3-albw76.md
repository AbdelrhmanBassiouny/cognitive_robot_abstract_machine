# PR #88 — P3: abstract→concrete-subclass expansion + first-order form

Status (2026-07-29): pushed (22 commits total, 872ea244a latest). Back in **draft** (converted
after this round's own push, per personal convention — the developer had marked it ready for
review after 88c95ed2's CI went green). Base `main`
(#86/#87 both merged there). Subscribed to activity. 17 review threads total, all now
reply-and-resolved except round 6 (reconciliation question, informational — nothing to resolve).
An unexpected `Claude <noreply@anthropic.com>`-authored merge-from-main commit (`6b51075e`) landed
directly on this branch mid-round-15, from outside this session — see the roadmap section above
for the full investigation and how it was reconciled (rebase, not force-push). Description
rewritten twice so far: once for the 2026-07-24 rebase, once for round 11's repeated-article
redesign; no further rewrite needed since (no user-visible surface change from any subsequent
round, only internal layering/bugfix/docstring/test/doctest-harness/consolidation wording, except
the limit-wording correction, which is a genuine (small) surface-text fix already covered by the
description's existing text). CI checked through 91e3ca4b: `krrood`'s own job green; a `coraplex`
job failure (an `ormatic_interface.py` regeneration/`ruff format` internal error) and the
recurring pre-existing `semantic_digital_twin` flake (`test_world_sim_state_sync`) both confirmed
unrelated to this PR. CI checked through 88c95ed2 (all 19 check runs): a "failure" webhook fired
while several jobs (`coraplex`, `krrood`, `giskardpy`, `semantic_digital_twin`) were still
in_progress; polled `get_check_runs` until they all finished — every job passed, including
`coraplex` (which just took ~28 minutes, longer than usual, and briefly looked like the source of
the failure webhook before it went green). No code fix was needed; the failure notification
appears to have reflected a transient/retried state, not an actual break. `mergeable_state` was
`clean` at that point. Hourly check-in loop active; PR still not merged/closed, so subscription
continues.

### Restacking conflict (2026-07-29): the stacking routine flagged a real merge conflict
An automated stacking-routine comment reported `main` had moved and merging it into this branch
conflicted in three files. Investigated by actually running `git merge origin/main` (not just
reading the routine's summary): the conflicts came from an unrelated `main` PR that renamed the
whole verbalization-testing snapshot mechanism — `SymbolicSurfaceSnapshot`→
`VerbalizationResultsOfPackage`, `VerbalizationSurface`→`VerbalizationResult`,
`surface_verification.py`→`result_verification.py`, plus a new `result_generation.py` that
auto-generates the snapshot module from `conftest.py` (mirroring how `ormatic_interface.py` is
regenerated). Two of the three conflicts were mechanical: `test_verbalization_surfaces.py`/
`verbalization_surfaces.py` are modify/delete conflicts superseded by the new auto-generated
`verbalization_results.py`/`test_result_generation.py`, so took the deletion and let the generator
reproduce the file (it already picks up this PR's abstract-subclass-expansion sentences correctly
once regenerated).

The third — `result_verification.py` itself — was more than a rename: `main` also replaced the old
per-instance `operand_overrides` mechanism (this PR's own reviewed design, from round 2/3: a
`SymbolicSurfaceSnapshot(operand_overrides={...})` instance-scoped override) with a single global
`PLACEHOLDER_EXAMPLE_VALUES` dict in production code, and dropped the free-standing
`placeholder_operands`/`first_order_form` functions this PR's own first-order-form work built on
("a caller wanting the first-order form of one class... can call it directly"). Confirmed via
`main`'s own new `test_result_generation.py` that the global registry is only ever populated with
real production classes (`HasType`/`HasTypes`) — there's no way for a test to supply its own
locally-scoped override (as `test_first_order_form.py`'s `Kindled`/`catalyst`→`"ash"` test does)
without either mutating that shared production dict from a test or losing the coverage. This is a
genuine design regression, not a simple rename, so instead of silently picking a side, asked the
developer directly via `AskUserQuestion` with the concrete tradeoff. Chosen: restore scoped
overrides. Implemented by keeping `main`'s global `PLACEHOLDER_EXAMPLE_VALUES` registry and its
`PlaceholderExampleField` key type, but adding an `operand_overrides` field back onto
`VerbalizationResultsOfPackage` — keyed by the *same* `PlaceholderExampleField` type (so there's
one key shape shared by both the global and instance-scoped registries, not two parallel ones) —
consulted after the global lookup in `placeholder_operands`. Restored the free-standing
`placeholder_operands`/`first_order_form` functions too, delegating to the global registry so they
stay consistent with the instance method. Updated `test_first_order_form.py` to the renamed
imports and the `PlaceholderExampleField`-keyed override dict, and fixed one stale
`surface_verification`→`result_verification` string reference in `test_rule_doctests.py`'s own
assertion. Full `test_verbalization/` suite green (761/3 skipped — one fewer than before since
`test_verbalization_surfaces.py`'s hand-written coverage is now `test_result_generation.py`'s),
full `test/krrood_test/` suite green (2013 passed, same 2 pre-existing unrelated `graphviz`
failures). Merge commit + a follow-up black-formatting commit pushed as 872ea244a. Replied on the
PR explaining the resolution and the reasoning behind the restored per-instance overrides;
converted back to draft per personal convention. CI for 872ea244a just started — check next
session/check-in.

### Round 16 (2026-07-28, 1 comment): `type_members` should accept any iterable
`type_members` (`value_lexicon.py`) only accepted `tuple`/`list`; the developer asked for any
iterable, matching `DisjunctivePhrase.as_fragment`'s existing "iterable, not str/bytes" pattern.
Fixed: `isinstance(value, (str, bytes)) or not isinstance(value, Iterable)` guard, then convert to
`list` and check every member is a `type`. Added a `set`-based doctest example (`sorted(...)`-
wrapped for determinism). `LiteralRule`/`OneOf` call sites unaffected (contract unchanged). Full
`test_verbalization` suite green (760/3 skipped), full `test/krrood_test` suite green (2012
passed, same 2 pre-existing unrelated `graphviz` failures). Pushed as d45003c7; reply-and-resolved.

### Round 17 (2026-07-28, 1 comment, same line as round 16): reuse the existing `is_iterable`
Immediate follow-up: "There's a helper for checking for iterables in krrood use it, and if needed
extend it." Found `krrood.entity_query_language.utils.is_iterable` (already the shared convention
across `comparator.py`, `base_expressions.py`, `variable.py`, `ripple_down_rules/utils.py`) and
swapped `type_members`'s inline check for it. No extension needed — `is_iterable` excludes
`str`/`bytes`/`bytearray` like the round-16 inline check did, but also excludes a bare `type`
itself, which the inline check didn't; that matters because a class's metaclass can define
`__iter__` (an `Enum` subclass iterates its members), so `is_iterable` rules a bare class out up
front rather than relying on the downstream `all(isinstance(member, type) ...)` guard to reject it
(which it would have, harmlessly — not a live bug, but `is_iterable` is more direct). Confirmed
`krrood.entity_query_language.utils` has no runtime-level internal imports (only a
`TYPE_CHECKING`-guarded one), so importing `is_iterable` into `value_lexicon.py` carries no
circular-import risk. Full `test_verbalization` suite green (760/3 skipped), full
`test/krrood_test` suite green (2012 passed, same 2 pre-existing unrelated `graphviz` failures).
Pushed as 88c95ed2; reply-and-resolved.

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
  companion test, plus two more docstring/AGENTS.md polish items. Pushed as ea595142.
- Round 15 (docstring narrative/all-caps cleanup + AGENTS.md rules, first_order_form doctest +
  doctest-harness extension to the `testing` package, missing `:param:` docs in
  `determiner_processor.py`) all reply-and-resolved. Pushed as 91e3ca4b, on top of an unexpected
  `Claude <noreply@anthropic.com>`-authored merge-from-main commit that appeared on this branch
  mid-round (see the roadmap section's "Unexpected merge on the branch" entry for the full
  investigation) — reconciled via a plain rebase (no force-push), one leftover unused import
  fixed, full suite re-verified green. All rounds now reply-and-resolved except round 6
  (informational, nothing to resolve). PR converted back to draft after this push per personal
  convention (was ready-for-review from the developer's own round-14 action).
- CI checked through 91e3ca4b (both `krrood`'s job and the wider run, given the unexpected
  main-merge underneath it — see round 15). The Type-verbalization consolidation (99ea09ee) and
  its follow-up correction (c1e95cbe, `FallbackNouns.name_of` → `type_noun` after all, per the
  developer overriding my initial "leave it" call — see the roadmap section's "Type-verbalization
  scatter audit"/"Follow-up correction" entries) are direct chat requests, not GitHub review
  rounds; CI for 99ea09ee/c1e95cbe/d45003c7 (round 16)/88c95ed2 (round 17, reuse `is_iterable`, see
  above) not yet checked — do that next session.
- `mergeable_state` reports "unstable" as of the last `get` call (2026-07-28) — re-verify against
  `main` next session; nothing outstanding was found the last time this was investigated (round
  6), but several commits have landed on both branches since.
- P4 (sdt = PR #33 rebase) still needs P1 + P2 + P3 all merged to main first.
