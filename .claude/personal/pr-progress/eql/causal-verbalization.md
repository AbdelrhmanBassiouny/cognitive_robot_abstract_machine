# eql/causal-verbalization (W2) — draft PR #82 -> claude/rdr-why-answer-6fnw2o

Session: https://claude.ai/code/session_01JCEFrP4eBx2pgmf5FarFLm
Branch: eql/causal-verbalization (base: W1 = claude/rdr-why-answer-6fnw2o).

## Plan
Verbalize RDR why-answers as causal explanations: "<conclusion> because
<conditions>, by the <kind> rule". "because" vocabulary + grammar/causal/
assembler (InferenceAssembler two-block pattern), routing beside the Match
special case, concrete-instance threading via binding_overrides,
WhyAnswer.verbalize().

## Done
- vocabulary/english.py: CausalConnectives enum (BECAUSE). Minimal diff (conflict
  watch: montessori_ijcai also edits this file; fragments/base.py +
  parts_of_speech.py untouched).
- verbalization/grammar/causal/: CausalPlanner + CausalStructure, CausalAssembler
  (conclusion clause + "because"-headed coordinated conditions + rule-identity
  clause), auto-registered CausalExplanationRule (construct=WhyAnswer).
- EQLVerbalizer.build/_scan_target + pipeline.verbalize: route WhyAnswer beside
  Match; dispatches through fold to CausalExplanationRule.
- Concrete case threaded via binding_overrides -> "the Animal" (definite) not
  "an Animal" (bare variable).
- WhyAnswer.verbalize() entry point (lazy import to avoid layering inversion).
- rdr->verbalization only; verbalization->rdr kept to local imports + the rules
  module (no import cycle; verified).
- test_causal_verbalization.py (12 tests) green; full test_eql_rdr (262) green;
  fixture-independent verbalization suite green; docformatter applied.
- Draft PR #82 opened, subscribed.

## Deferred / next
- Concessive "although" clauses for non-fired refinements: WhyAnswer does not
  expose non-fired sibling refinements, and raw rule-tree conditions do not
  verbalize in isolation (Refinement/Query nodes). Needs a W1 trace-selection
  extension; seam is in place (two-block assembler + CausalConnectives).
- Optional DiscourseScopeRule so the case pronominalizes into the because-clause
  ("... because it is milk"); currently repeats "the Animal".
- Watch PR #82 CI; the fixture-gated verbalization tests + ORM gen need py3.12,
  so full verbalization suite is confirmed on CI, not locally.
