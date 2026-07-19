PR #82 (eql/causal-verbalization -> claude/rdr-why-answer-6fnw2o), draft, RDR
causal-explanation verbalization + rule codes. Working branch:
claude/pr-82-causal-review-t6ppd2.

Status: review round DONE, plus one CI-caught regression fixed. All 22
threads replied-and-resolved (20 resolved, 2 left open pending PR #83 — the
boolean-predicate goldens). Pushed commit f9fa1252 (rebased cleanly onto a
mid-session remote restack, zero file overlap) then commit 2bb7503e (a
CI-caught fix, see below) to eql/causal-verbalization. Author+committer both
set to the human identity throughout. PR description updated to match the
diff, session link kept. PR stayed draft throughout (per personal-notes
default).

CI-caught regression (commit 2bb7503e): the krrood test_each_lib job failed
with `AttributeError: 'WhyAnswer' object has no attribute 'rule_kind'` in
test_why.py — a file I never touched, missed because my earlier "is rule_kind
read anywhere?" grep only covered krrood/src, not test/. Fixed both
assertions to use `answer.rule_code.kind.tree_connector_word` (the field's
replacement) instead of the removed `answer.rule_kind`. Verified: (a) a
comprehensive re-grep of the whole test/ tree for rule_kind/from_kind/
CausalConnectives/.verbalize()/_annotate_rule_comments turned up nothing else
missed; (b) an isolated WhyAnswer dataclass construction confirms the
attribute chain resolves to "if"/"except if" correctly; (c) local end-to-end
verification is blocked by a pre-existing `jpt` import-chain gap in
.why()'s evaluation path (same class of pre-existing local-env gap
documented elsewhere in these notes, not something my fix caused — confirmed
by every test in the class failing identically at setUp(), not just the two
I touched). Real verification is CI, which has the full env.

CI: re-check pending on 2bb7503e. Still expect only test_each_lib (coraplex)
to fail per the developer's stale-base note — not touching it, no
rebase/merge attempted beyond fast-forwarding through the restack's own merge
commits (zero overlap with files this PR touches, verified via
`git diff --name-only <old-base> origin/eql/causal-verbalization` before
doing it).

Lesson for next time: when removing a field/method, grep the WHOLE repo
(test/ included, not just src/) before concluding it's unread.

What shipped this round (see the PR description for the full writeup):
- rule_tree_view.py: RuleView.kind is RuleKindWord directly now (no
  string<->enum conversion, no _KIND_STRING_TO_WORD global); added
  RuleKindWord.tree_connector_word (match/case, not a dict) for the ASCII-tree
  wording.
- why.py: dropped the now-redundant rule_kind field (rule_code.kind covers
  it); WhyAnswer.verbalize() removed entirely (callers use
  verbalize_expression(answer)) — this also removed rdr/why.py's last
  reference to verbalization, so nothing needs to stay inline-imported there.
- serialization.py: rule-comment placement is now structural — an
  identity-keyed AST sentinel statement emitted during _emit_rule_body,
  swapped for a real `#` comment post-unparse by exact marker match (not a
  substring guess on "add("). Added the missing rule_code_map param doc.
  Verified byte-for-byte identical output via the self-contained
  test_serialization.py fixtures (no zoo dataset needed).
- english.py: Conjunctions/CausalConnectives split into
  CoordinatingConjunctions (FANBOYS: for/and/nor/but/or/yet/so) and
  SubordinatingConjunctions (because/although/though/unless/whereas/once/
  lest/while) as two sibling classes — the real grammatical distinction, not
  a "Connectives" wrapper. Renamed Conjunctions at all ~18 call sites across
  the grammar package (flagged the blast radius before doing it; developer
  said go ahead).
- pipeline.py/verbalizer.py: if-chains -> match/case; pipeline.py's dead
  WhyAnswer no-op branch removed by construction, and its WhyAnswer import
  along with it (verbalizer.py's WhyAnswer import stays — genuinely used —
  just hoisted to top level).
- causal/planner.py, causal/assembler.py: WhyAnswer import hoisted out of
  TYPE_CHECKING to real top-level (empirically verified no cycle: temp-edited,
  ran both import orders, reverted, full suite unaffected); quotes dropped
  for real on the Planner[WhyAnswer,...]/Assembler[WhyAnswer,...] base-class
  subscripts (these are eager-evaluated even under `from __future__ import
  annotations`, since that only defers *annotations* not base-class
  expressions — that's why they were quoted at all).
- binding_scope.py: BindingScope's docstring re-scoped off "instantiated
  variable" framing now that CausalAssembler is a second, unrelated consumer
  of the generic binding_overrides map.
- Rejected/discussed-away: no new Rule datastructure (RuleView/RuleCode
  serve genuinely different traversal orders); no Question ABC for
  Match/Query/WhyAnswer (match/case covers the actual need; the real O/C
  dispatch already exists via fold/select/RULES).
- Test updates (API-change consequences, not test-gaming): test_rule_code.py
  swapped test_kind_from_rdr_kind_string for
  test_tree_connector_word_matches_the_ascii_view_vocabulary (from_kind no
  longer exists). test_causal_verbalization.py: ~15 answer.verbalize() call
  sites -> verbalize_expression(answer); dropped
  test_verbalize_method_matches_pipeline (moot once one side of the
  comparison no longer exists).
- Verified zero regressions: test_eql_rdr (25 failed/125 passed/122 skipped)
  and test_eql/test_verbalization (2 failed/649 passed/3 skipped/34 errors)
  both match the unmodified baseline exactly (confirmed via git stash
  comparison) — every failure is a pre-existing local-env gap (missing
  random_events.variable / probabilistic_model.probabilistic_circuit /
  pandas pieces), none caused by this diff.
- Formatting: caught and reverted two rounds of over-eager blanket
  reformatting (black's py3.12-target Template-literal compaction unrelated
  to my edits; scripts/format_docstrings.py rewrapping every pre-existing
  single-line docstring in serialization.py/parts_of_speech.py to multi-line,
  per the repo's own docformatter config, which the committed code doesn't
  actually follow yet) — reverted both to keep the diff scoped to what this
  PR actually needs, ran black --fast per-file instead.

Remaining for next session:
1. Confirm CI is green (or still just the known coraplex stale-base failure)
   on the new commit.
2. PR #83 (boolean-predicate verbalization) merges -> annotate the zoo
   Animal dataset fields with the declared predicates, update the two open
   goldens ("is milk"/"is feathers" -> "has milk"/"has feathers"), reply and
   resolve the last 2 threads.
3. Watch for any new review activity (still subscribed).

Prior-round context (superseded, kept for history):
- Fetched latest, checked out eql/causal-verbalization tracking origin.
- Subscribed to all PR activity.
- CI: confirmed only test_each_lib (coraplex) fails (stale-base artifact per the
  developer's note); all other 17 jobs green. Not touching it (no rebase/merge).
- get_review_comments (GraphQL) is hitting "API rate limit already exceeded for
  user ID 36744004" — retried repeatedly over ~20 min, still blocked. Proceeding
  from the developer's detailed task-description summary of the review, which I
  cross-verified line-by-line against the actual source (every file:line
  reference checked out exactly). Still need real thread IDs/text before I can
  reply-and-resolve on GitHub — retry get_review_comments once rate limit clears.
- Read rdr/rule_tree_view.py, rdr/serialization.py, rdr/why.py, verbalizer.py,
  pipeline.py, causal/planner.py, causal/assembler.py, english.py in full.
- Set up a local py3.11 test env (pip-installed typing_extensions, colorama,
  ordered_set, jinja2, rustworkx, sqlalchemy, numpy, scipy, casadi, inflect,
  lemminflect, pytest, and editable-installed ./random_events) and got
  test_eql_rdr running: baseline is 25 failed / 125 passed / 123 skipped, all
  25 failures pre-existing env gaps unrelated to this PR (missing
  random_events.variable / probabilistic_model pieces, e.g. parameterizer.py).
  test_causal_verbalization.py + test_rule_code.py currently all skip (zoo
  dataset needs network/ucimlrepo or a cached pickle that isn't present locally)
  except test_rule_code's 5 non-skipIf unit tests, which pass.
- Empirically verified (temporary edits, reverted, confirmed via git status
  clean) that hoisting the inline `from krrood...rdr.why import WhyAnswer` in
  both pipeline.py (~142) and verbalizer.py (~98) to top-level imports, plus
  causal/planner.py's TYPE_CHECKING-gated one, works fine in both import orders
  and the full test_eql_rdr suite still shows the same 25 pre-existing
  failures (no new breakage). Root cause: rdr/why.py has ZERO top-level
  dependency on verbalization — the only real cycle edge is WhyAnswer.verbalize()'s
  own deferred import of verbalization.pipeline. That's the one inline import
  that must stay (or be removed if verbalize() itself goes away, see below).

Architecture assessment (to present to the developer before coding):
1. Rule datastructure (serialization.py top): NOT a full new `Rule` god-object
   (RuleView already has depth for ASCII-tree display; RuleCode already has
   id/kind for naming; conflating them adds coupling with no payoff — YAGNI).
   Narrower real fix: `rule_code_map()` currently does TWO tree walks
   (`walk_rules_in_emission_order` + `rule_kinds()` which internally re-walks
   via `walk_rules`) to get index+kind, when `_flatten_selector_chain`'s
   `ConclusionSelectorBranch.conclusion_selector_type` (Refinement/Alternative/
   Next) already carries the kind info structurally during the SAME walk that
   assigns the index. Recommend: thread kind through
   `walk_rules_in_emission_order` (or a sibling helper) so `rule_code_map`
   needs one walk, not two.
2. RuleView.kind / RuleKindWord duplication (rule_tree_view.py ~178/~215):
   real duplication, confirmed. `walk_rules`'s `visit()` hands the ASCII-tree
   renderer raw kind strings ("if"/"except if"/"else if") separately from
   RuleKindWord's prose words ("base"/"refinement"/"alternative"), bridged by
   `from_kind` + the module-global `_KIND_STRING_TO_WORD` map. Recommend:
   make `RuleView.kind: RuleKindWord` directly (walk_rules assigns real enum
   members, not strings — also satisfies AGENTS.md "use enums not strings");
   add a `RuleKindWord` property (e.g. `.tree_connector_word`) for the
   "if"/"except if"/"else if" ASCII-view wording, so ONE enum owns every
   kind-related wording and the global map + from_kind conversion disappear.
   Consequence: WhyAnswer.rule_kind (str) becomes fully redundant with
   WhyAnswer.rule_code.kind (confirmed: rule_kind is written in from_trace but
   never read anywhere else in the codebase, not even in tests) — recommend
   deleting the field, not just retyping it. rule_depth is also currently
   unread outside its own assignment, but the PR description explicitly
   reserves it for the deferred "although" concessive-clause follow-up, so
   flagging it rather than silently removing it.
3. Rule-code comment placement (serialization.py ~448/449): confirmed fragile
   — `_annotate_rule_comments` substring-matches `line.lstrip().startswith("add(")`
   on already-unparsed text. Recommend emitting the comment structurally
   during AST generation instead (e.g. as a `ast.Expr` sentinel/marker
   statement inserted alongside each `add(...)` in `_emit_rule_body`, keyed by
   node identity, then rendered/stripped-to-comment post-unparse at the same
   point) rather than re-deriving position by parsing rendered text. Need to
   check ast_helpers/CodeGenerator for the cleanest way to carry a comment
   through an ast.unparse round-trip (Python's ast.unparse drops comments
   entirely, which is presumably why substring search was used — the
   structural fix still needs to happen post-unparse, but keyed by walking the
   SAME ordered_nodes/statement structure the emitter used, not by re-parsing
   text for a literal "add(" prefix). Still finalizing the concrete mechanism.
4. CausalConnectives taxonomy (english.py ~478): no existing "Connectives"
   grouping class in this file — every VocabEnum subclass here (Keywords,
   Logicals, Copulas, Prepositions, Conjunctions, ...) is a flat sibling
   namespace, several with only 1-4 members (Directive has 2, Logicals has 4),
   so a 1-member CausalConnectives class fits the established pattern, not an
   outlier. Recommend against inventing a new class-hierarchy tier for one
   word (YAGNI). Lean towards merging BECAUSE into the existing `Conjunctions`
   enum (already the closest sibling, placed directly above it) with an
   updated docstring noting it covers both coordinating (and/or) and
   subordinating (because) conjunctions — but want the developer's take before
   touching it, since `Conjunctions.AND` is used in a structurally different
   role (list-joining conjunction=... parameter) than BECAUSE (a BlockFragment
   header), so merging is a naming/taxonomy simplification only, not a
   behavioral one.
5. Match/Query/Why if-ladder (verbalizer.py ~60/100, pipeline.py routing):
   pushback on a `Question` ABC spanning Match/Query/WhyAnswer — they are
   three unrelated class hierarchies today (Match: Evaluable +
   AbstractMatchExpression + HasFactoryAndKwargs; Query: SymbolicExpression-
   based; WhyAnswer: a plain frozen dataclass), and grepped confirmed no
   existing "Question" concept anywhere outside rdr/why.py's own WhyQuestion.
   The actual polymorphic dispatch for verbalization content already exists
   (fold/select/RULES) and is already open-closed; this if-ladder is a
   narrow 3-line "make sure lazy state is built before folding" prebuild
   step, not the core dispatch. Forcing Match and Query (both large,
   widely-used core classes far outside this PR's diff) to inherit a new ABC
   for that would be disproportionate. Recommend: convert the if-chain to
   match/case (satisfies the "if-chains -> match/case" ask directly) and drop
   the do-nothing WhyAnswer branch by construction (case _: falls through).
   Want the developer's agreement before ruling out the heavier ABC design.
6. why.py:~124 / verbalizer.py:~98 / pipeline.py:~142 inline imports: mostly
   NOT a real cycle needing to stay inline — see the empirical test above.
   Recommend hoisting pipeline.py's and verbalizer.py's `WhyAnswer` imports to
   top-level. rdr/why.py's own deferred import of verbalization.pipeline
   inside `verbalize()` is the one genuine cycle-breaking edge; whether it
   stays deferred depends on item 7 below.
7. WhyAnswer.verbalize() (why.py ~128): genuinely a 1-line pass-through to
   verbalize_expression(self) with no other logic. Leaning towards deleting it
   and having callers use verbalize_expression(why_answer) directly — this
   also removes rdr/why.py's only remaining reason to reference verbalization
   at all, cleanly resolving item 6's last inline import too. But this is a
   call site (usage-pattern) fix affecting the docstring's 'the entry point
   over the plain pipeline' framing and every test that calls
   `answer.verbalize()` (test_causal_verbalization.py uses it repeatedly as
   the primary API) — want the developer's confirmation before removing public
   API surface a whole test file is written against.
8. causal/assembler.py ~63 (_bind_case_instance / should not be
   planner/assembler's concern): Planner must not touch fragments (see
   Planner's own docstring), so the NounPhrase construction structurally
   cannot move to CausalPlanner — the current placement (in realize()) is
   actually the only layer allowed to do it, matching the established
   precedent in grammar/instantiated/assembler.py's own binding_overrides use.
   BUT: found a real, more precise problem — `BindingScope` (binding_scope.py)
   is docstring-scoped explicitly to "verbalizing an instantiated variable"
   and bundles instantiated-variable-only `constraint_frames` alongside the
   generic `binding_overrides` id->fragment map; CausalAssembler is the map's
   second, unrelated consumer (repurposing it for "known concrete case ->
   definite reference", not field-reference reuse within one instantiated
   variable's where-clause). engine.py reads binding_overrides generically
   (not instantiated-variable-specific), so the MECHANISM is fine to reuse;
   only the class's docstring/framing is stale. Leaning towards: re-scope
   BindingScope's docstring/naming to describe binding_overrides generically
   (decoupled from "instantiated variable"), not moving the logic elsewhere.
   Want the developer's read on whether that's the concern they meant, or
   something else — this is the DISCUSS item I'm least sure I've correctly
   diagnosed without the literal comment text.
9. Test "why do we need this" items: `if __name__ == "__main__": unittest.main()`
   at test_causal_verbalization.py:246 and test_rule_code.py:130 both match
   test_why.py's identical convention (the file test_causal_verbalization.py's
   own docstring says it mirrors) and 11/25 files in test_eql_rdr/ use it —
   established suite convention, not dead weight. Plan: reply justifying, no
   code change, resolve those two threads.
10. Boolean-attribute surfaces (test_causal_verbalization.py ~79, ~136):
    confirmed dependency on PR #83 (not yet checked whether merged). Plan:
    reply noting the dependency, no change yet — do not hand-fake surfaces.

Next steps:
1. Retry get_review_comments to get literal thread text + IDs (blocking
   reply/resolve on GitHub); reconcile my inferred understanding against the
   actual wording, especially item 8 above.
2. Present items 1-8 to the developer as an architecture DISCUSS message
   before writing any code (per instructions).
3. Once agreed: implement architecture changes first, then the mechanical
   list (serialization.py ~253 param docs; planner.py ~54 / causal/assembler.py
   ~38 quoted-hint cleanup — check whether these are real annotations
   `from __future__ import annotations` already covers, or base-class-subscript
   forward refs like causal/planner.py's `Planner["WhyAnswer", ...]` that
   need TYPE_CHECKING+hoist instead; pipeline.py ~144/146, verbalizer.py ~100
   match/case + dead-branch removal).
4. Reply-and-resolve every thread per the workflow (justify-only threads
   resolved directly; architecture threads resolved once the agreed fix is
   pushed).
5. Update the PR description to match the final diff; keep session link.
6. Flag the coraplex CI failure / restack need explicitly in a chat message
   (not a code fix).
