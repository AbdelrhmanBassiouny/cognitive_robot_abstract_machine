# eql/causal-verbalization (W2) — draft PR #82 -> claude/rdr-why-answer-6fnw2o

Session: https://claude.ai/code/session_01JCEFrP4eBx2pgmf5FarFLm
Branch: eql/causal-verbalization (base: W1 = claude/rdr-why-answer-6fnw2o).
Siblings: boolean-predicate PR #83 (eql/attribute-predicate-verbalization.md,
off main); handles the "is milk" bug generally (this branch still shows "is
milk" until that lands).

## Done (commit 1 — causal grammar)
- CausalConnectives(BECAUSE) + grammar/causal/ (planner+assembler+auto rule),
  routing beside Match, concrete-instance via binding_overrides,
  WhyAnswer.verbalize(). test_causal_verbalization green.

## Done (commit 2 — rule codes)
- rule_tree_view: RuleKindWord (base/refinement/alternative -> R/R/A) + RuleCode
  (id + kind compare=False -> id-only eq/hash; as_string "R0"/"R1"/"A2") +
  rule_kinds(). serialization.rule_code_map(): id = emission (file) order index,
  base R0, keyed by condition._id_ (verbalizer & serializer agree by identity;
  the two walks differ so keying by position would drift).
- WhyAnswer.rule_code (from_trace); CausalStructure carries it; _rule_identity_clause
  -> "by the <kind> rule <code>", code a RULE_REFERENCE-role token (new SemanticRole
  + link-blue colour) for later linking.
- serialization emits "# <kind> rule <code>" above each add(...), in file order
  (self-documenting + link anchor).
- Surgically re-applied to rule_tree_view/serialization to avoid docformatter
  churning pre-existing docstrings (black-clean; CI gates on pytest not fmt).
- test_rule_code.py + causal goldens updated; full test_eql_rdr (273) green.

## Deferred / next
- Phase 2 (separate PR): clickable rule-code link to the serialized-RDR line +
  conditions-on-hover (HTML). Needs a generalized reference/tooltip in the core
  renderer (SourceReference is Python-symbol-only; tooltip hard-coded to docstring)
  + an RDRRuleLinkResolver, and the RDR persisted (save_path). Groundwork done:
  RULE_REFERENCE fragment + serialized-file anchors.
- Concessive "although" clauses for non-fired refinements (needs W1 trace ext).
- Watch PR #82 CI (pushed commit 2). Fixture-gated verbalization tests + ORM gen
  need py3.12; confirmed on CI.
