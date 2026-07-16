# PR plan: rdr/feature-capture — KA-time feature capture (Wave 1, Track F, PR 2/2)

Not started. Base: `rdr/feature-registry`. Design:
`rdr_architecture_plan.md` §2.1 (capture, dedup, autocomplete).

## Goal

When the expert writes new logic in the IPython interface, capture it as a
**named feature**: append it to the per-case-type feature module (reusing
the rules-to-source serialization pipeline), register it, and make it
available to all future rules.

## Components

- `%feature <name>` magic in `rdr/magics.py` (thin adapter; logic lives in
  a `FeatureCapture` class beside the registry).
- **AST-hash dedup:** normalize the captured expression's AST, hash,
  compare against the registry; on near-duplicate, suggest the existing
  feature instead of storing a copy. `FeatureDeduplicator` as its own
  small class (SRP) so the normalization strategy is swappable.
- **Autocomplete:** registered feature names appear in shell completion on
  the case variable (extend the `__dir__` union that already merges the
  case type's attributes).
- Persistence: feature modules written beside the fitted model files via
  `RDRFileStore`-style lifecycle (do not reinvent file handling).

## TDD anchors

1. Capture a feature in a simulated shell (`shell_runner` seam); assert it
   lands in the module file, registry, and a later rule resolves it.
2. Capturing an AST-equivalent duplicate suggests the existing feature and
   does not double-register.
3. Completion offers the captured feature on `case_variable.<tab>`.
