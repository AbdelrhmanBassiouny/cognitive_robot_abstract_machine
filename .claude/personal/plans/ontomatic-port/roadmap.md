# Ontomatic port: roadmap

## Sources

- **Fork `aamas27-experiments`** = `dl` + 13 `[Ontomatic]` commits (2026-10-06): the full
  Ontomatic (`krrood/src/krrood/ontomatic/{ontology_to_python, property_descriptor, utils.py,
  alternative_mappings.py}`) and `test/krrood_test/test_ontomatic/` (6 files). This is the code
  the paper's experiments ran on.
- **`cram2/main`** has only `ontomatic/property_descriptor/` and `failures.py`, evolved separately
  (`krrood.patterns.role.Role`, `krrood.symbol_graph`, `krrood.patterns.caching`).
- **Fork `aamas27-unification-revision`** (contains `aamas27-fast-translation`): 15 EQL/ORMatic
  commits on the 2026-10-05 main, no PR anywhere yet.
- **Paper**: `AbdelrhmanBassiouny/krrood_aamas` (LaTeX). **Experiments**:
  `AbdelrhmanBassiouny/krrood_experiments` (`dl`, `aamas27-*`). **Supplement**:
  `formalization/rl_rules_table.tex` maps all 78 OWL 2 RL/RDF rules; 6 unsupported
  (cls-nothing2, cls-svf2, cls-oo, dt-not-type, scm-eqc2, scm-eqp2), 18 partial.

## Why a rewrite-in-place rather than a merge

The branch targets the old EQL API (`entity_query_language.entity`, `.symbolic`,
`.symbol_graph`, `class_diagrams.utils.Role`), uses relative imports, the external
`ripple_down_rules` package, `line_profiler`, `typing`, string-keyed dicts, a 2 325-line
`owl_to_python.py` and a 1 720-line `OwlLoader`. Upstream's `property_descriptor` diverged by
+1 025/-236 lines.

## Decisions (user, 2026-10-13)

- The paper's EQL/ORMatic work is a separate track in this plan; only
  `eql-correlated-quantifiers` blocks Ontomatic (generated object properties are collections).
- TBox domain/range derivation uses explicit OWL rules (prp-dom/rng via inverse, equivalent and
  super-properties; scm-dom2/rng2); the generated RDR files are dropped.
- Going past RL is native Python; no Java reasoner in the library. HermiT results may only be
  stored as test fixtures, with any live-reasoner test skipped in CI and paired with them.

## Rules every item follows

- One immutable, typed `Terminology` read from RDF once; compiler, loader and check all read it.
- Every construct is classified (materialized / checked / query-time / unsupported); nothing is
  dropped silently - unsupported constructs raise or appear in the profile report.
- Each realized OWL 2 RL/RDF rule is a class named for what it does, carrying its W3C rule id;
  the loader and the check iterate a registry of them.
- `OwlLoader` becomes Algorithm 1's steps as single-responsibility classes sharing a load state.
- Reuse upstream: `krrood.code_generation`, `krrood.patterns.role`, `krrood.symbol_graph`,
  `krrood.patterns.subclass_safe_generic`.
- AGENTS.md: absolute imports, `typing_extensions`, dataclasses, StrEnums, custom exceptions,
  `# %%` sections, tests first; krrood stays self-contained (test ontologies as `.owl`/`.ttl`
  files and mimic classes under `test/krrood_test/dataset/`).

## Known bugs to fix during the port (model-compiler unless noted)

- All sufficient conditions of a class are conjoined, so a class with two `∃P.D ⊑ C` axioms is
  never classified: they are a disjunction.
- `owl:Thing` as a filler and `owl:Nothing` as a superclass break loading or importing.
- Subclass/subproperty cycles make the generated module fail to import.
- `line_profiler`/`tqdm`/timing inside library code (abox-loader).

## Gates

- After `closure-verification`: Ontomatic's closure equals owlrl's on every dataset ontology; the
  rule-coverage test lists no rule as missing without a reason.
- After `owl2bench-experiments`: OWL2Bench (1 university) matches the supplement's
  `results/REPORT.md` (3 667 individuals, 1.42 M assertions).
- After `el-classification`: LUBM's classification matches the stored HermiT hierarchy.
