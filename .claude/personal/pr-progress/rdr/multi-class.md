# PR plan: rdr/multi-class — MCRDR port (Wave 1, Track G, PR 1/2)

Not started. BLOCKED until the Wave-0 stack lands on main. Design:
`rdr_architecture_plan.md` §2.2 + legacy `krrood/ripple_down_rules` MCRDR
as reference (design reference only — do not import from it). Base: `main`.

## Goal

`EQLMultiClassRDR`: multiple independent conclusions per case (the `Next`
union edge in `conclusion_selector` already encodes MCRDR semantics at the
EQL level). Lifts the current single-valued-attribute guard in
`rdr/underspecified.py` (iterable inference targets currently rejected
with "future MultiClassRDR").

## Design

- LSP first: extract the shared fit/classify contract from
  `EQLSingleClassRDR` into an abstract `EQLRuleTreeClassifier`
  (`classify`, `fit_case`, tree ownership, save_path) so single- and
  multi-class are substitutable wherever the backend consumes them.
- `EQLMultiClassRDR` composes the same observer/insertion machinery;
  wrong-conclusion refinement anchors per fired conclusion root
  (`on_conclusions_processed` fires per root — verify).
- Stopping-conclusion semantics (legacy MCRDR's "stopping rule") modelled
  as an explicit conclusion type, not a magic value.
- `rdr/backend.py::RDRBackend` picks the classifier per
  `(case type, attribute)` cardinality — scalar → single-class, iterable →
  multi-class — behind the shared abstraction (OCP: no isinstance chains
  at call sites).

## TDD sequence

1. Failing test: underspecified query with an iterable target attribute
   currently raises — pin the new expected behaviour (multi-class model
   created, multiple conclusions yielded).
2. Zoo-style dataset gains a multi-valued attribute in the test dataset
   (mimic classes, krrood-self-contained).
3. Port fit loop: multiple experts rules per case, refinement on wrong
   subset, cornerstone checks.
4. Serialization round-trip for a multi-class tree (unparser already
   handles Next edges? verify, extend if not).
