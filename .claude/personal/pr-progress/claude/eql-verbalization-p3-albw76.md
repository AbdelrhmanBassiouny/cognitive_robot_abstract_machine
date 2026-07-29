# PR #88 — P3: abstract→concrete-subclass expansion + first-order form

**MERGED to `main` (2026-07-29).** This PR is finished — no further work on this branch.
P1's and P2's commits are carried in this branch's history too (see "What's done" below for
why); P4 (sdt = PR #33) is the only remaining phase — see
`.claude/personal/plans/eql-verbalization/roadmap.md` for its checklist. Session unsubscribed
automatically on merge.

Final status: 26 commits total, fd4f91f7c latest (then rebased twice more onto out-of-session
merges — see "Restacking conflict" and its round-20 follow-up below — final head c185b648d,
then fd4f91f7c again after round 22; the PR merged at that point). Base `main` throughout since
the 2026-07-24 rebase (retargeted from P2's branch, #86/#87 both merged there by then). 22
numbered review threads total plus two direct-chat design discussions (the Type-verbalization
scatter audit and its follow-up correction), all reply-and-resolved except round 6
(informational, nothing to resolve). CI for fd4f91f7c (pre-round-22, first push of that content):
all 20 checks completed — 19 passed (including `krrood`'s own job), 1 failure on
`semantic_digital_twin`'s known pre-existing `test_world_sim_state_sync` physics-settling flake
(871 passed, 1 failed — confirmed via `get_job_logs`, unrelated to this PR's files); no code
change needed. CI checked through 91e3ca4b: `krrood`'s own job green; a `coraplex` job failure
(an `ormatic_interface.py` regeneration/`ruff format` internal error) and the recurring
pre-existing `semantic_digital_twin` flake both confirmed unrelated to this PR. CI checked
through 88c95ed2 (all 19 check runs): a "failure" webhook fired while several jobs were still
in_progress; polled `get_check_runs` until they all finished — every job passed, including
`coraplex` (which just took ~28 minutes, longer than usual, and briefly looked like the source of
the failure webhook before it went green) — a transient/retried state, not an actual break.
Description rewritten twice: once for the 2026-07-24 rebase, once for round 11's
repeated-article redesign; no further rewrite needed after that (no further user-visible surface
change, only internal layering/bugfix/docstring/test/doctest-harness/consolidation wording,
except the limit-wording correction, which the description's existing text already covered).

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
- **Review round 4** (`first_order_form` overrides question, pushed 19280e06): a truly
  value-agnostic rendering needs nothing external, so `operand_overrides` had no business on the
  general `placeholder_operands`/`first_order_form` signatures — moved into
  `SymbolicSurfaceSnapshot` itself, which layers its own registered overrides on top. Resolved.
- **Review round 5** (test-quality question, pushed 68cea9fd): the override test asserted the
  overridden and un-overridden renderings were *equal* — proved nothing, since the mimic
  predicate's fragment never read the overridden field. Gave the mimic's fragment a second clause
  reading that field too, so the override's effect became genuinely visible in the rendered
  sentence. Resolved.

### 2026-07-24 rebase
Base retargeted from P2's branch to `main`, now that #86+#87 had merged there. `main` had ~5 days
of substantial unrelated activity by then — a `code_generation` package extraction,
`robokudo`/`semantic_digital_twin` work, `surface_verification.py` moved to
`krrood.entity_query_language.testing.surface_verification`, and P2's own continued review round
moving `Distinguisher` to an ABC hierarchy and `GrammarMetadata` to
`krrood.entity_query_language.verbalization.grammar_metadata`. CI had failed with
`ImportError: cannot import name 'GrammarMetadata'` — fixed the two stale
`krrood.patterns.field_metadata` imports (`referring.py`, `test_operand_referring.py`) to the new
module, confirmed the only other CI failure (`test_world_sim_state_sync` in
`semantic_digital_twin`) is an unrelated pre-existing flaky physics-settling test. Then merged
`main` into the branch directly (3 conflicts, all mechanical import-only: `referring.py`'s import
block, a duplicate `GrammarMetadata` import in `test_operand_referring.py`, an unused
`SymbolicCallable` import in `verbalization_surfaces.py` — verified via a disposable `git
worktree` trial merge first that nothing deeper conflicted, given `Distinguisher`'s ABC refactor
lives in the same file) and fixed `test_first_order_form.py`'s import of `surface_verification`
to the new `testing` package path. `mergeable_state` now `clean`; PR base retargeted to `main`;
description updated to reflect the now-focused diff (7 files, +733/-72, no more phantom P1/P2
content). Full `test/krrood_test/` suite green (2012 passed, 9 skipped) apart from two
pre-existing unrelated failures (`graphviz`/`dot` missing in this sandbox). black + docformatter
applied throughout.

- **Review round 6** (2026-07-25, reconciliation question): asked whether the branch was still
  reconciled with `main` and the `VerbalizationSurface` changes. Checked `git log` for commits on
  `main` since the 2026-07-24 rebase touching `krrood/entity_query_language/verbalization/` or
  `krrood/entity_query_language/testing/` — none (the ~78 newer commits are all unrelated
  `semantic_digital_twin`/`ripple_down_rules`/mujoco/robocasa work). Replied confirming, not
  resolved (informational).
- **Review round 7** (`_concrete_type_alternatives`/`operand_type_alternatives` returning
  `Optional[Tuple[...]]`, 2 comments): "why not just return an empty tuple?" — both functions,
  `NounForm.type_alternatives`, and `ReferringExpressions.type_alternatives_of` now use `()`
  throughout instead of `None`/`Optional`; `_HeadNounGrouping.add`'s `type_alternatives` param
  defaults to `()` too. Both threads reply-and-resolved.
- **Review round 8** (`disjunctive_type_head`'s manual `oxford_comma`/`Conjunctions.OR` call):
  "isn't there a `DisjunctivePhrase` in parts of speech that does exactly this?" — yes; swapped
  the manual join for `DisjunctivePhrase(alternatives).as_fragment()`. Resolved (this function's
  role narrowed further in round 11 — see below).
- **Review round 9** ("cannonical" ambiguous, 2 comments): renamed every "canonical"-family
  identifier in `referring.py` to "representative" — `canonical_of`→`representative_of`,
  `noun_of_canonical`→`noun_of_representative`, `canonicals_by_noun`→`representatives_by_noun`,
  `members_by_canonical`→`members_by_representative`, `_noun_of_canonical`→
  `_noun_of_representative`, `_type_alternatives_of_canonical`→
  `_type_alternatives_of_representative`, plus local variables and docstrings. Verified a
  case-insensitive grep for "canonical" across the file afterward returns zero matches. Both
  threads reply-and-resolved.
- **Review round 10** ("make all these classes as dataclasses", `test_operand_referring.py`):
  `@dataclass`-decorated every mimic class lacking it — `Shape`/`Circle`/`Square`,
  `Instrument`/`Drum`/`Flute`/`Harp`, `Polygon` and its seven concrete subclasses, `ConcreteBase`/
  `ConcreteBaseVariant`, `Sensor` — plus the equivalent classes in `test_first_order_form.py`
  (`Igniter`, `Fastener`/`Bolt`/`Screw`) for consistency, since the same rule applies there too
  though not explicitly flagged. Resolved.
- **Review round 11** (the repeated-article pushback — "shouldn't there be an `a` before
  square?"): the shipped divergence (one shared article, *"a Body or Region"*) was wrong; the
  developer wanted decision 3's original *"a Body or a Region"*. A naive fix (bake a second
  article into the disjunctive text, leave the outer phrase's determiner bare) would have been
  wrong on repeat/definite mention (*"the Circle or a Square"*, mixed definiteness). Instead
  `NounPhrase` gained `additional_heads: List[VerbalizationFragment]` — further disjunctive heads
  sharing the phrase's definiteness/number/alternative/ordinal, each choosing its own article
  independently. `DeterminerProcessor._lower_noun_phrase` now builds one determiner-and-head group
  per head (factored into a new `_head_group` helper) and joins them with "or" (Oxford-comma style
  at 3+, via the existing `oxford_comma`); falls back to exactly the old single-head behaviour when
  `additional_heads` is empty, so the ~10 other `NounPhrase` call sites are unaffected.
  `VariableRule.build` now constructs the `NounPhrase` directly from `NounForm.type_alternatives`
  (first alternative as `head`, rest as `additional_heads`) instead of going through
  `disjunctive_type_head`, which is now solely `operand_head_noun`'s internal same-noun
  grouping-key text generator. Updated the affected end-to-end sentences (*"a Circle or a Square is
  warm"*, *"a Drum, a Flute, or a Harp is warm"*, `first_order_form`'s *"a Bolt or a Screw is
  secure"*). Full `test_verbalization/` suite green (756/3 skipped); full `test/krrood_test/` suite
  unchanged from the 2026-07-24 baseline (2012 passed, same 2 pre-existing unrelated `graphviz`
  failures). Pushed as commit 33a8da5b; PR description rewritten to describe the repeated-article
  design instead of the old shared-article trade-off. Resolved.
- **Review round 12** (2026-07-26, 4 comments): (a) `NounPhrase.additional_heads` design question
  — "why must they be distinct alternatives, why a separate attribute, discuss with me." Replied
  with reasoning rather than a code change: distinctness isn't required or checked (a caller could
  pass duplicates, they'd just render pointlessly, e.g. "a Body or a Body"); considered unifying
  `head`+`additional_heads` into one `heads: Tuple[...]` but rejected it — `head` is structurally
  special (ordinal/pre_head attach only there, it's the phonology anchor for the ordinary
  non-disjunctive case), so merging would hide that asymmetry behind an implicit "index 0 is
  special" rule instead of stating it in the type, and would touch ~20 unrelated
  `NounPhrase(head=...)` call sites for no benefit. Recommended keeping the shipped shape; **left
  unresolved**, awaiting the developer's response (explicit "discuss with me"). (b) "Isn't this
  more grammatically correct than a single article? Discuss with me" (defending the
  repeated-article choice) — replied with the concrete argument: a shared article is provably
  wrong the moment two alternatives need different articles (e.g. `Apple`/`Banana` — no single
  "a"/"an" works for both), which `_concrete_type_alternatives` can't rule out since it accepts
  any abstract base's subclass names; repeated article is immune by construction. Cited
  Fowler's/CGEL as secondary style support. **Left unresolved** (explicit discuss request). (c) "Is
  it fine that referring.py imports from parts_of_speech? Shared low-level impl instead?" — a real
  layering violation: `parts_of_speech.py` (vocabulary) already imports from
  `microplanning.coordination`/`possessive`, so `referring.py` (microplanning) importing back from
  `parts_of_speech` crossed the boundary both ways. Fixed: added `disjunctive_phrase()` to
  `microplanning.coordination` (next to the near-identical existing `one_of()`); both
  `DisjunctivePhrase.as_fragment` and `disjunctive_type_head` now call it, and `referring.py`'s
  import of `vocabulary.parts_of_speech` is gone entirely. Resolved. (d) "Representative what? Same
  problem as canonical, needs a complementary word" — round 9's rename fixed the ambiguous word but
  left "representative" bare as a noun in several docstrings; standardized on "representative
  referent" throughout the file (every field docstring in `DistinguisherIndex`/`_HeadNounGrouping`,
  `distinguisher_for`, `add`, `head_nouns`, `type_alternatives`, `_group_referents_by_noun`,
  `referent_aliases`). Resolved. Pushed as commit a4a69b06; full `test_verbalization/` suite green
  (756/3 skipped), full `test/krrood_test/` suite unchanged (2012 passed, same 2 pre-existing
  `graphviz` failures).
- **Review round 13** (2026-07-26, 3 comments, same day as round 12): (a) the grammar-
  justification thread (round 12b) got no further reply from the developer — they resolved it
  themselves after reading the Apple/Banana argument, no action needed. (b) follow-up on the
  `additional_heads` design thread (round 12a): "Ok keep it, however I'd like to see how this
  behaves — e.g. re-mentioning the variable elsewhere in the query." Built exactly that scenario
  (`and_(AbstractOperandRole(shape), VisibleFromSensor(shape, sensor))` — a second, non-pronoun
  mention) and it exposed a real bug: `CoreferenceProcessor._reduced()` (the definite-repeat-mention
  path) rebuilt `NounPhrase` from scratch naming only head/number/definiteness/referent_id/
  alternative/ordinal — `additional_heads` was never listed, so a repeat mention silently dropped
  every alternative but the first ("the Circle" instead of "the Circle or the Square"). `_rebuilt()`
  had a milder version (preserved via `replace()` but never walked). Fixed both to propagate + walk
  `additional_heads` exactly like `head`; added a permanent regression test
  (`test_reused_abstract_operand_reads_as_a_definite_disjunction_on_repeat_mention`). Resolved. (c)
  "Don't mention users/callers in a docstring, it goes stale — add this to AGENTS.md" (on
  `disjunctive_phrase`'s docstring, which had named `DisjunctivePhrase`/`disjunctive_type_head` as
  its "the shared building block behind" callers) — reworded to describe behavior/contract only;
  added the rule to `AGENTS.md`'s Documentation section. Resolved. Also fixed, unprompted but same
  underlying issue: an awkward doubled "representative referent *representative*" docstring phrase
  from round 12's rename pass (developer flagged it directly) — reworded. Pushed as commit
  e66bf4b5; full `test_verbalization/` suite green (757/3 skipped, +1 for the new regression test),
  full `test/krrood_test/` suite green (2013 passed, same 2 pre-existing unrelated `graphviz`
  failures).
- **Review round 14** (2026-07-26, 3 comments, same day as round 13): (a) round 13's `add`
  docstring fix ("the representative referent *representative* names") was itself flagged "again
  awkward wording" — simplified further by dropping the attempt to redefine "representative"
  inline entirely; the method now just says "Record *referent_id* as a member of *representative*,
  registering it under *noun* …", relying on the class's own field docstrings to already establish
  what a representative referent is. Resolved. (b) "Will these ever pronominalise to 'it'? Maybe in
  a full query? Add tests" (on the repeat-mention regression test from round 13) — yes; added
  `test_reused_abstract_operand_pronominalises_on_every_mention_within_its_scope`, the pronoun
  companion to round 13's definite-repeat test: a disjunctively-typed variable as a full
  entity-query subject pronominalises to "it" on *every* mention inside that WHERE scope (not just
  the first repeat), while the one spelled-out first mention keeps the full disjunction — together
  the two tests cover both branches `CoreferenceProcessor` can take on a repeat mention of a
  disjunctive head. Resolved. (c) "Point AGENTS.md's docformatter rule at the actual repo script
  instead" — changed "Always run `docformatter`..." to "Always run `scripts/format_docstrings.py`
  (black + docformatter)...", matching what every P1–P4 session actually runs. Resolved. Pushed as
  commit ea595142; full `test_verbalization/` suite green (758/3 skipped, +1 for the new pronoun
  test), full `test/krrood_test/` suite green (2014 passed, same 2 pre-existing unrelated
  `graphviz` failures). Also noted: CI on this same head SHA showed a `coraplex` job failure (an
  `ormatic_interface.py` regeneration/`ruff format` internal error) and the recurring pre-existing
  `semantic_digital_twin` flake (`test_world_sim_state_sync`) — both confirmed unrelated to this PR
  (neither touches any file this PR changes; the `coraplex` one is an ORM-generation issue this
  session correctly left alone per AGENTS.md's guidance never to hand-fix `ormatic_interface.py`).
  `krrood`'s own job passed.

### Unexpected merge on the branch (2026-07-27, discovered mid-round-15)
Pushing round 15's commit hit a non-fast-forward rejection —
`origin/claude/eql-verbalization-p3-albw76` had moved to a merge commit (`6b51075e`, "Merge
remote-tracking branch 'origin/main'") authored as `Claude <noreply@anthropic.com>` — **not by
this session**, and in direct violation of AGENTS.md's Version Control rule (commits must be the
human identity, never an assistant identity/`noreply@anthropic.com`). Investigated before doing
anything: diffed my last commit against that merge commit's tree for the one file it touched that
overlaps this PR (`test_operand_referring.py`) and confirmed every P3 class/test survived intact —
the only real change was a one-line `FieldMetadata(other_metadata=[...])` → `GrammarMetadata(...)`
update reflecting an unrelated main-branch API simplification. Did **not** attempt to rewrite or
force-push to fix the bad authorship (that would rewrite already-pushed shared history
unilaterally, which AGENTS.md and this session's own conventions rule out without explicit
permission) — instead did a plain `git rebase origin/<branch>` (safe: only replays this session's
own not-yet-pushed commit, touches nothing already on the remote), fixed one resulting unused
`FieldMetadata` import the merge's API change left behind, verified the full suite, and pushed
normally (fast-forward, no force). Flagged the authorship-policy violation to the user for their
awareness; not something to silently ignore, but also not something to unilaterally "fix" via
history rewrite.

- **Review round 15** (2026-07-27, 3 comments): (a) "docstrings read like a conversation, talk
  about hypothetical bad designs instead of being short/to the point, no comparison, no historical
  context — make this a rule in AGENTS.md and apply everywhere; also don't scream words in all
  caps, check and fix everywhere; apply the formatting script to all modified files." Added both
  rules to AGENTS.md's Documentation section. Trimmed every narrative/comparison docstring this
  PR's `additional_heads` work had introduced (`NounPhrase.additional_heads`,
  `disjunctive_type_head`, `NounForm.type_alternatives`, `DeterminerProcessor._head_group`,
  `CoreferenceProcessor._reduced`) down to plain statements of behavior. Fixed the three leftover
  ALL-CAPS "VALUE" instances in `surface_verification.py` (pre-existing from P1, not this round's
  own writing, but part of this PR's diff) to RST `*value*`. Ran `scripts/format_docstrings.py` on
  every touched file. Resolved. (b) "`first_order_form`/`placeholder_operands` missing a doctest
  example, and it needs to be added to the auto-tested doctests" — added `>>>
  first_order_form(IsReachable)` / `placeholder_operands(IsReachable)` examples (reusing the same
  shared example-domain predicate every other doctest in the codebase already uses); discovered
  `surface_verification.py` lives in `krrood.entity_query_language.testing`, outside the
  `verbalization` package `test_rule_doctests.py` auto-discovers by walking, so the new doctest
  would have silently never run — extended that harness to also walk the `testing` package and
  added a regression test locking in the new coverage. Resolved. (c) "add and check parameter
  docstrings everywhere" (on `determiner_processor.py`) — `_head_group` had zero `:param:` entries
  for its 4 parameters and `_lower_noun_phrase` had a `:return:` but no `:param:`; added both.
  Resolved. Pushed as commit 91e3ca4b (on top of the unexpected merge, reconciled as above); full
  `test_verbalization/` suite green (760/3 skipped), full `test/krrood_test/` suite green (2012
  passed — count shifted from the unrelated main-merge's own test changes, not this PR — same 2
  pre-existing `graphviz` failures). PR was ready-for-review (developer's own action from round
  14's check-in); per personal convention, converted back to draft after this round's push.

### Type-verbalization scatter audit (2026-07-28, direct chat question, not a GitHub review comment)
Developer asked whether Type-verbalization logic is spread across too many places and to discuss
before fixing. Dispatched a research subagent to map every call site under `verbalization/` that
renders a Python `type`. Finding: mostly a clean layered pipeline (`type_noun` →
`RoleFragment.for_type`/`for_value` → `disjunctive_phrase`/`one_of` → `referring.py`'s
abstract→concrete expansion → `OneOf`/`DisjunctivePhrase` → `HasType`/`HasTypes`) — most
cross-file references are legitimate reuse, not duplication. Three exceptions found and discussed:
(1) "is this a homogeneous tuple/list of classes" reimplemented 3x (`value_lexicon.value_phrase`,
`LiteralRule._type_members`, `OneOf`'s `are_types`); (2) `value_phrase`'s tuple-of-types branch is
dead code (shadowed by `LiteralRule`'s own tuple handling) *and* contradicts it (joins with "or",
unlinked, vs. `LiteralRule`'s "and", linked); (3) "class name with a fallback" written 3x
(`type_noun`, `FallbackNouns.name_of`, `InstantiatedPlanner._type_name`), neither of the latter two
delegating to `type_noun`. User approved fixing all three. Fixed (1)+(2): extracted
`type_members()` to `value_lexicon.py`, pointed `LiteralRule`/`OneOf` at it, deleted
`value_phrase`'s dead/contradictory branch. **Did NOT fix (3)** after empirically testing it
first: routing `FallbackNouns.name_of` through `type_noun` broke `test_limit_verbalization.py` — a
bare-`int`-typed query subject is *regression-tested* to read "the top three ints" (raw lowercase
`__name__`), a deliberately different grammatical role from `type_noun`'s "Integer" value/literal
convention, not an accidental duplicate; reverted that one change. Also left
`InstantiatedPlanner._type_name` alone — its `_type_` is typed `Union[Type[T], Callable]`, broader
than `type_noun` safely handles (a `functools.partial`-like callable lacking `__name__` would crash
it), so unifying would be a regression risk for a case that isn't really "the same thing" after
all. Pushed as commit 99ea09ee; full `test_verbalization/` suite green (760/3 skipped), full
`test/krrood_test/` suite green (2012 passed, same 2 pre-existing `graphviz` failures).
`mergeable_state` now reports `clean`.

### Follow-up correction (2026-07-28, same day)
Developer overrode the (3) decision above — "the limit verbalization should [read] the top three
Integers", i.e. the `int`-as-query-subject wording that `test_limit_verbalization.py` had locked in
("the top three ints") was itself the stray inconsistency, not a deliberate convention; the fix
should go through after all. Re-applied `FallbackNouns.name_of` → `type_noun`, and updated all 6
affected assertions in `test_limit_verbalization.py` to the "Integer"/"Integers" wording (a
legitimate spec correction from the developer, not test-cheating — AGENTS.md's "never modify the
test when fixing a failing test" is about not papering over a bug, not about refusing an explicit
behavior-change instruction from the person who owns the intended output). Verified this was the
*only* test file affected by grepping the full suite run. Pushed as commit c1e95cbe; full
`test_verbalization/` suite green (760/3 skipped), full `test/krrood_test/` suite green (2012
passed, same 2 pre-existing `graphviz` failures).

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
converted back to draft per personal convention.

- **Review round 18** (2026-07-29, 1 comment, on the merge/restack commit): developer proposed a
  better design for `PLACEHOLDER_EXAMPLE_VALUES` itself — a per-class method (like
  `_verbalization_fragment_`) instead of a global dict, explicitly asking to discuss and be
  critical before implementing. Agreed it's a real improvement, for a reason beyond the one
  stated: the global dict can only ever hold entries for `krrood`'s own classes (`HasType`/
  `HasTypes`) since `krrood` must stay self-contained (AGENTS.md) and can never import another
  workspace package's predicate class to add an entry for it — a real layering violation the
  just-merged `main` design can't avoid once `semantic_digital_twin` needs its own override (P4
  almost certainly will). A per-class method sidesteps this entirely. Flagged one thing not to
  assume away: this PR's own `test_first_order_form.py` `Kindled`/`catalyst`→`"ash"` override is a
  different kind of thing (test-mechanism-proving, not a domain truth about `Kindled`), so
  recommended keeping the just-restored per-instance `operand_overrides` for that case alongside
  the new class method for "field is intrinsically never a real operand." Asked two clarifying
  questions before implementing: (1) exact method signature — proposed
  `_example_operands_(cls, operands: Dict[str, Any]) -> Dict[str, Any]` taking/returning the raw
  placeholder-operands dict (not `RenderedFields`, which is post-render), default identity; (2)
  host class — proposed `SymbolicCallable` (which is what `placeholder_operands` already types
  `cls` as) over the developer's stated `Verbalizable` (`SymbolicCallable` is currently
  `Verbalizable`'s only subclass, so moot in practice, but asked rather than assumed). Replied, not
  yet resolved — awaiting the developer's answer before implementing.
- **Review round 19** (2026-07-29, same day, 1 comment): developer clarified the override method is
  "just for the testing and for the generation verbalization results... not for normal usage at
  all" — confirming `_example_operands_` must be consulted only by `VerbalizationResultsOfPackage`,
  never by the free-standing `placeholder_operands`/`first_order_form`. Implemented: added
  `SymbolicCallable._example_operands_(cls, operands)` (default identity), overridden on
  `HasType`/`HasTypes` for `types_`; deleted `PLACEHOLDER_EXAMPLE_VALUES`/`PlaceholderExampleField`
  entirely; kept the per-instance `operand_overrides` (now `Dict[Type[SymbolicCallable], Dict[str,
  Any]]`, no more shared key type since the global registry is gone) for
  `test_first_order_form.py`'s test-scoped `Kindled`/`catalyst`→`"ash"` case; went with
  `SymbolicCallable` as the host class per the round-18 question (unanswered but unobjected-to).
  Added a new `Gauge` mimic (a real operand field + one overridden via `_example_operands_`) with 3
  tests proving the free functions ignore the override while the snapshot applies it. Pushed as
  commit 9892e2ba4; full `test_verbalization/` suite green (764/3 skipped, +3 new tests), full
  `test/krrood_test/` suite green (2016 passed, same 2 pre-existing unrelated `graphviz` failures).
  Reply-and-resolved.
- **Review round 20** (2026-07-29, same day, 3 comments): (a) "why manually add `**operands`? can't
  we just add what we want to add?" — a real simplification: `_example_operands_` never actually
  depended on the rest of the placeholder dict, so dropped the parameter entirely —
  `_example_operands_(cls) -> Dict[str, Any]` now just returns the override values (`{"types_":
  int}` for `HasType`), and `VerbalizationResultsOfPackage.placeholder_operands` merges them in
  itself. (b) "very big header docstring, summarize it a lot, describe what is, not what was
  before" — trimmed `result_verification.py`'s module docstring from 4 paragraphs to 2. (c) "why
  extra quotes around `ash`?" (on the `Kindled`/`catalyst`→`"ash"` test assertion) — explained this
  is pre-existing `value_lexicon.value_phrase` behavior (any non-type/enum/datetime literal renders
  via `repr(value)`, so a plain string always renders quoted), already visible elsewhere in the
  codebase (`VariableRule._domain_choice`'s own doctest: *"one of 'Sales' or 'Eng'"*); no code
  change needed there, just an explanation. All 3 reply-and-resolved. Pushed as commit 138f40e43,
  then rebased (no force-push) onto another unexpected `Claude <noreply@anthropic.com>`-authored
  merge that landed on the branch mid-round from outside this session (`f5d1c8831`, merging in an
  unrelated plan-dashboard-skill PR #479 — verified zero overlap with this PR's own files via `git
  diff` before rebasing) → final commit c185b648d. Full `test_verbalization/` suite green (764/3
  skipped), full `test/krrood_test/` suite green (2016 passed, same 2 pre-existing unrelated
  `graphviz` failures).
- **Review round 21** (2026-07-29, same day, follow-up on round 20c): developer asked for "a
  copyable prompt that actually removes these quotes cleanly from all string values," reasoning
  Type/Enum values are already differentiated by colour/hyperlinks. Checked that claim before
  drafting anything: `PlainFormatter` (`rendering/formatter.py`) has **no** colour/hyperlink markup
  at all — only `ANSIFormatter`/`HTMLFormatter` do — and `verbalize_expression`'s default path
  (`VerbalizationPipeline.plain()`) uses `PlainFormatter`, as does virtually every existing test and
  every committed snapshot. So today the quotes are the *only* plain-text signal distinguishing a
  literal value from a bare noun; dropping them unconditionally is a real design question, not a
  safe mechanical cleanup. Did not implement anything (out of scope for this focused P3 PR — it's a
  cross-cutting change to `value_lexicon.value_phrase`'s core convention, would touch every
  package's committed snapshot). Instead drafted a self-contained, copyable prompt for a follow-up
  session: states the goal, leads with the `PlainFormatter` caveat as the first thing to resolve
  (don't assume the answer), narrows the actual code change to `value_phrase`'s `str` case
  specifically (not a blanket `repr()` removal, since `int`/`float`/`bool` already render
  unquoted), and lists the follow-up work (docstring/doctest update, regenerate every package's
  snapshot, grep+update hardcoded quoted-string assertions). Posted as a reply, thread resolved (no
  code change requested in this PR).
- **Review round 22** (2026-07-29, same day, 2 comments): (a) "rename to
  `_example_operand_values_`" — renamed the hook everywhere (`SymbolicCallable`/`HasType`/
  `HasTypes` in `predicate.py`, `result_verification.py`, both test files' mimics and docstrings).
  (b) "remove any mentions of methods or classes, the two-line summary above is enough" (on
  `result_verification.py`'s module docstring, already trimmed once in round 20b) — cut it further
  to just the two-line summary, nothing else. Both reply-and-resolved. Pushed as commit fd4f91f7c;
  full `test_verbalization/` suite green (764/3 skipped), full `test/krrood_test/` suite green
  (2016 passed, same 2 pre-existing unrelated `graphviz` failures). No further out-of-session merge
  landed this round (checked via `git fetch` before pushing — clean fast-forward). PR merged
  shortly after.

## Final state
All 22 numbered review rounds plus both direct-chat design discussions reply-and-resolved (round
6 stayed informational, nothing to resolve). P1's and P2's own review-round history is recorded
separately under their own branches
(`pr-progress/claude/eql-verbalization-p1-surface-verification-eqltzc.md`,
`pr-progress/claude/eql-verbalization-operand-naming-n0gb95.md`). P1, P2, and P3 are all now
merged to `main`; P4 (sdt = PR #33) is the only remaining phase in the `eql-verbalization` plan.
