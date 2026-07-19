# eql/attribute-predicate-verbalization — draft PR #83 -> main

Session: https://claude.ai/code/session_01JCEFrP4eBx2pgmf5FarFLm
Branch: eql/attribute-predicate-verbalization (base: main).
Sibling: causal PR #82 (its note lives under eql/causal-verbalization.md).

## Plan
Fix boolean-attribute condition verbalization ("an Animal is milk" was wrong).
Per-field BooleanPredicate + verbalization realization + name-shape heuristic
default; negation derived via morphology (do-support / copula suppletion),
number via Clause. Review response (commit d657d928) restructured per user's 3
approved forks + negation-scope "either".

## Done (original)
- Predicate family + heuristic + ChainAssembler rewire + tests + draft PR #83 off main.

## Done (review response, commit d657d928, rebased onto adcfed2e)
- A: moved GrammarMetadata -> verbalization/grammar_metadata.py; predicate types
  -> verbalization/boolean_predicate.py; patterns/field_metadata.py keeps only
  FieldMetadata; deleted layering-guard test.
- B: collapsed spec+realizer into one polymorphic BooleanPredicate (each builds
  own head/predicate_object); removed registry + UnknownBooleanPredicateError;
  builders take the terminal Attribute node (no loose owner+name).
- C: dropped Article -> Definiteness; complement -> predicate_object; spec ->
  predicate; morphology AdjectivalSuffix(StrEnum); heuristic honesty docs;
  unquoted type hints; param/field docs.
- D: "either" placement by negation scope (OPERATOR/copula -> after head;
  VERB/do-support -> fronts head). Goldens: "either has milk or not",
  intransitive "either breathes or not", kept "is either operational or not".
- Tests green (86 touched-file tests); black + docformatter; committed as human.
- PR #83 description updated; all 29 review threads replied + resolved; kept draft.

## Review round 2 (commit 1ef0b157) — DONE
- Added real per-field docstrings to test mimics (my first "done" was false).
- Removed the LLM aside from default_boolean_predicate docstring.
- CI green on 1ef0b157 (all 18 checks incl. coraplex/krrood/sdt).
- Both remaining threads now settled by user:
  1. adjective library — user: "fine as it is now, do nothing." Kept suffix
     heuristic; thread resolved.
  2. either-placement — user wants it as its own follow-up PR in a NEW session;
     asked for a study-first/plan-with-options/discuss prompt (not prescribe a
     solution). Prompt handed off in chat; thread left OPEN as the tracking marker.
- PR #83 review fully addressed. User marked it READY FOR REVIEW themselves
  (2026-07-19) — leave it ready (their explicit action); do not re-draft.

## Deferred / next
- Follow-up PR (new session): move open-boolean "either" placement out of
  boolean_alternative_clause into a realization/negation pass (options: polarity
  feature on head + clause-level RealizationPass, or alternatives). Off main.
- Cross-lib CI watch (coraplex/sdt goldens may shift); fixture-gated tests need py3.12.
- Causal PR #82 (branch eql/causal-verbalization) — big review (~22 comments) arrived.
  Investigated: #82 is STACKED on a deep unmerged chain (base
  claude/rdr-why-answer-6fnw2o -> D-core-*/RDR-refactor stack; W1 NOT in main), so
  the coraplex test_merge_motions CI red is a stale-base artifact of the STACK and
  needs a RESTACK via the user's restacking workflow, NOT a rebase-onto-main from me
  (that would replay the whole stack). Do NOT attempt a manual rebase/merge here.
  Recommendation accepted by planning: handle the WHOLE #82 review (mechanical +
  architecture) in one fresh dedicated session, because the mechanical fixes land on
  the same files the architecture redesign rewrites (serialization.py,
  rule_tree_view.py, pipeline.py, verbalizer.py, english.py). Handoff prompt drafted
  in chat. Central architecture theme: replace string-based rule kind + post-hoc
  string-search comment annotation with a structured Rule/kind (RuleView.kind ->
  StrEnum unified with RuleKindWord; drop from_kind + the global map) and emit the
  code comment structurally during generation; plus Question base class for
  Match/Query/Why (open-closed), Connectives parent for the causal connective, and
  the mechanical batch. That session maintains #82's own pr-progress note
  (eql/causal-verbalization.md) via save-pr-progress.sh; I did NOT touch #82.
- Boolean-attr dependency: once #83 lands, annotate zoo Animal fields + update #82
  causal goldens ("because the Animal has milk").
- Note: this sits alongside the PR #33 P1-P4 roadmap (PRs #86/#87/#88/#33) in the
  personal notes — separate work, situational awareness only.
