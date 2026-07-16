# PR plan: rdr/concept-trees — NRDR concept layer (Wave 2)

Not started. BLOCKED on Track F (`rdr/feature-registry`) and Track G
(`rdr/general-fixpoint`). Design: `rdr_architecture_plan.md` §2.2–2.3.
Likely splits into 2–3 stacked PRs at execution time; keep this note as
the umbrella plan.

## Goal

Expert-defined **named concepts, each an RDR tree** (nested RDR): concept
conclusions become vocabulary other trees/rules may reference; refining a
concept fixes all consumers at once — with a safety net so shared edits
cannot silently break downstream knowledge.

## Components

1. **Concept declaration** — a tree can be declared a *concept tree*
   (vocabulary) vs *domain-output tree*; a conclusion may be both
   (Species). Explicit dataclass declaration, not string tags.
2. **Stratified evaluation** — order the fixpoint passes by the
   `DependencyGraph` strata (fewer passes); falls back to naive order on
   cycles (monotonicity keeps cycles safe — Wave 1 guarantees).
3. **`SemiNaiveFixpoint(EvaluationStrategy)`** — per pass, re-fire only
   trees whose referenced conclusions gained facts in the previous pass.
   Drop-in strategy next to `NaiveFixpoint`; property-style test: same
   fixpoint as naive on randomized tree sets.
4. **Cornerstone-regression gate** — editing a concept tree (or a shared
   feature) re-runs the cornerstone cases of all downstream trees (walk
   the dependency graph); an edit that flips any downstream conclusion is
   rejected/flagged with a report object. This extends RDR's own
   cornerstone validation to the shared layer.
5. **Upstream-fix routing (UX hook)** — when a downstream rule misfires
   because an upstream concept was wrong, the KA interface offers refining
   the upstream tree instead of patching every consumer. Engine side here;
   interactive surface rides the D-ui layer.

## TDD anchors

- Concept referenced by two consumers; refine the concept once; both
  consumers' classifications change; their cornerstone regression passes.
- Downstream-flip edit is rejected with the offending cornerstone named.
- Semi-naive == naive fixpoint equivalence test.
