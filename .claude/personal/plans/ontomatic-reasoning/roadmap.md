# Ontomatic reasoning: standing rules

- The OWL 2 RL gaps are the supplement's: `formalization/rl_rules_table.tex` in
  `AbdelrhmanBassiouny/krrood_aamas` maps all 78 OWL 2 RL/RDF rules, 6 unsupported (cls-nothing2,
  cls-svf2, cls-oo, dt-not-type, scm-eqc2, scm-eqp2) and 18 partial.
- Each gap is its own PR, proven by a failing test first, and extends the rule registry and
  `Terminology` ontomatic-port builds rather than adding a parallel path.
- Every construct is classified as materialized, checked, query-time or unsupported; nothing is
  dropped silently, so an unsupported construct raises or appears in the profile report.
- Going past RL is native Python: sound always, complete where a tractable procedure exists, and
  explicit about the rest. No Java reasoner in the library (user, 2026-10-13).
- HermiT results may only be stored as test fixtures; any live-reasoner test is skipped in CI and
  paired with the fixture test (user, 2026-10-13).
- Gate: after `el-classification`, LUBM's classification matches the stored HermiT hierarchy.
