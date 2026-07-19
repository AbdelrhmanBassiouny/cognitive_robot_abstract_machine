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
- PR #83 review fully addressed. Still draft; do not mark ready unless told.

## Deferred / next
- Follow-up PR (new session): move open-boolean "either" placement out of
  boolean_alternative_clause into a realization/negation pass (options: polarity
  feature on head + clause-level RealizationPass, or alternatives). Off main.
- Cross-lib CI watch (coraplex/sdt goldens may shift); fixture-gated tests need py3.12.
- Causal PR #82: (a) coraplex test_merge_motions CI failure is a STALE-BASE artifact
  (main green on that job; #83 green on coraplex too) — rebase #82 onto main + re-run,
  awaiting user go-ahead; (b) annotate zoo Animal fields + update causal goldens
  ("because the Animal has milk") once #83 lands.
