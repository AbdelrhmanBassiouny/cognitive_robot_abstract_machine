# PR plan: rdr/oo-definitions — OO integration (Wave 3)

Not started. BLOCKED on `rdr/concept-trees`. Design:
`rdr_architecture_plan.md` §2.4–2.6. Harvest the prototypes on draft PRs
#21 (`rdr/oo-recognition`: recognition/ package — definition, engine,
registry, candidate generators, has_candidates, predicates,
test_recognition) and #22 (`rdr/backend-unification`), then close both.

## Goal

Classes own their recognition knowledge (Specification pattern) and the
engine resolves the **dependency graph between class definitions**
bottom-up — definitions never call definitions.

## Components

1. **`ClassDefinition` protocol** — a domain class exposes a definition
   RDR (e.g. `Drawer.definition`); serialized rule source lives beside the
   class; its cornerstone cases double as regression tests. Pure function
   `(candidate, scoped_view) -> judgment (+ explanation)`; no mutation.
2. **Inversion of control** — a definition *references conclusions*
   ("contains a body classified Handle"), never invokes
   `Handle.definition` imperatively. The Wave-2 engine supplies upstream
   conclusions per the dependency graph (class-definition edges are just
   concept-tree edges: Handle → Drawer).
3. **`CandidateGenerator` protocol** — cheap recall-oriented EQL
   structural query per class; deliberately over-generates; zero expert
   judgment. Registered via a discoverable per-class protocol (decorator
   vs classmethod vs registry — decide during grounding; #21 prototyped a
   registry).
4. **Case = `(candidate, scoped view)`** — scoped accessor into the
   candidate's neighborhood (Law of Demeter boundary), not the whole
   world.
5. **Taxonomy discriminators** — exclusive siblings (Drawer vs Cabinet)
   discriminated at the shared parent (Container) level; cross-cutting
   non-exclusive concepts (Openable) as independent binary definitions.

## Note on test data

All scenarios via the krrood-self-contained mimics in
`test/krrood_test/dataset/semantic_world_like_classes.py` (both prototype
PRs already extended it — reuse).
