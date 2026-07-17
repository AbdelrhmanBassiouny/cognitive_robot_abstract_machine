# eql/attribute-predicate-verbalization — draft PR #83 -> main

Session: https://claude.ai/code/session_01JCEFrP4eBx2pgmf5FarFLm
Branch: eql/attribute-predicate-verbalization (base: main).
Sibling: causal PR #82 (its note lives under eql/causal-verbalization.md).

## Plan
Fix boolean-attribute condition verbalization ("an Animal is milk" was wrong).
Per-field BooleanPredicateSpec (patterns) + verbalization interpreter +
name-shape heuristic default; negation derived via morphology (do-support /
copula suppletion), number via Clause. Decisions: heuristic default,
FieldMetadata-only, separate PR first (this one).

## Done
- patterns/boolean_predicate.py: BooleanPredicateSpec family (Adjectival /
  Possessive / Verbal) + Article enum; data-only (no verbalization import, so
  GrammarMetadata in patterns can reference it). GrammarMetadata.boolean_predicate.
- verbalization/attribute_predicates.py: realizer registry (concrete_subclasses),
  resolve_boolean_predicate + default heuristic (is_past_participle +
  is_likely_adjective suffixes -> "is X"; else "has X"; verbs need explicit spec),
  boolean_predicate_clause / boolean_alternative_clause. No grammar import (no cycle).
- morphology.is_likely_adjective (suffix fallback). exceptions.UnknownBooleanPredicateError.
- ChainAssembler.boolean_predicative/boolean_alternative -> Clause via interpreter;
  negation via negated flag; subject now pronominalizes ("... it is operational").
- Updated goldens: characterization_coverage (pronominalization x2); annotated
  mimics decaf + _NavPanel.lit (AdjectivalPredicate) since heuristic can't classify.
- test_boolean_predicates.py (22 tests) green; full fixture-independent
  verbalization suite 678 passed; docformatter applied. Committed as human author.
- Draft PR #83 opened off main. Subscribe pending (tool needed approval - retry).

## Deferred / next
- Cross-lib CI: booleans render differently everywhere; other libs' goldens may
  shift (coraplex/sdt). Confirmed only krrood test_verbalization locally; watch CI.
- Fixture-gated verbalization tests + ORM gen need py3.12 (run --confcutdir to skip
  the parent conftest locally); full suite confirmed on CI.
- Follow-up on causal PR #82: annotate zoo Animal fields + update causal goldens
  ("because the Animal has milk") once this lands.
