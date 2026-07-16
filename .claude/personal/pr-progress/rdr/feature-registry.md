# PR plan: rdr/feature-registry — feature layer core, the "poor man's Rete" (Wave 1, Track F, PR 1/2)

Not started. BLOCKED until the Wave-0 stack lands on main. Design:
`rdr_architecture_plan.md` §2.1. Base: `main`.

## Goal

Named, pure, memoized derived features that rules reference **by name
only** — one computation per case per inference run regardless of how many
rules use the feature (shared condition evaluation ≈ Rete's node sharing,
done via memoization instead of a beta network).

## Design (SOLID split — keep these as separate small classes)

- `rdr/features/feature.py::Feature` — frozen dataclass value object:
  `name`, `case_type`, `callable`, `source` (via
  `krrood.code_generation` source extraction). Pure; no engine knowledge.
- `rdr/features/registry.py::FeatureRegistry` — per-case-type registry
  (register / resolve-by-name / iterate). Raises a custom
  `UnknownFeature` exception; no silent fallbacks.
- `rdr/features/case_view.py::CaseView` — wraps a case instance; memoizes
  each feature's value on first access (the Rete-ish sharing point). One
  view per case per inference run, owned by the evaluation context, not
  global.
- Resolution hook (DIP): EQL attribute lookup on a case variable consults
  an `AttributeSource` abstraction — implementations: raw-dataclass source
  (default, existing behaviour) then feature-registry source. The engine
  depends on the abstraction; adding sources never modifies the engine
  (OCP). Decide during grounding whether the hook lives in
  `CanBehaveLikeAVariable.__getattr__` resolution or in an eql_rdr-specific
  wrapper — prefer the wrapper first (no core-EQL change), promote later
  only if needed.

## TDD sequence

1. Failing test: two rules referencing the same feature evaluate it once
   (counter in a test feature) — the memoization contract.
2. Failing test: rule condition resolves a registered feature by name over
   a `CaseView`; unknown name raises `UnknownFeature`.
3. Implement Feature/Registry/CaseView; wire the AttributeSource chain.
4. Integration: an `EQLSingleClassRDR` fit where the expert condition uses
   a feature name; serialize → reload → still resolves.

## Explicitly out of scope (PR 2/2 `rdr/feature-capture`)

IPython %feature capture magic, AST-hash dedup + near-duplicate
suggestion, registry autocomplete in the shell. Same file layout;
capture appends to the per-case-type feature module using the existing
rules-to-source pipeline.
