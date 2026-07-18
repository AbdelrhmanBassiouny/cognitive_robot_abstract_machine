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

## Review round 2 (commit 1ef0b157)
- Added real per-field docstrings to test mimics (my first "done" was false).
- Removed the LLM aside from default_boolean_predicate docstring.
- 3 threads resolved. 2 left OPEN awaiting user decision:
  1. either-placement: reviewer wants it out of boolean_alternative_clause into a
     realization/polarity pass (Polarity.OPEN on head + clause-level RealizationPass
     placing "either" by copula-vs-do-support). Proposed; asked this-PR vs follow-up.
  2. adjective library: list not exhaustive; offered WordNet membership check (adds
     nltk dep, over-classifies homographs) vs keep suffix heuristic. Asked preference.

## Deferred / next
- Awaiting user decision on the 2 open threads above.
- Cross-lib CI watch (coraplex/sdt goldens may shift); fixture-gated tests need py3.12.
- Follow-up on causal PR #82: annotate zoo Animal fields + update causal goldens
  ("because the Animal has milk") once this lands.
