# RDR Architecture Plan — Feature Sharing, Concept Trees, and OO Integration

**Status:** Design brief — output of a design conversation, to be grounded against the actual codebase before implementation.
**Scope:** `krrood/entity_query_language/eql_rdr` (the new EQL-based RDR library). The legacy `krrood/ripple_down_rules` package is backward-compatibility only and out of scope except as a reference for feature parity (MCRDR, GRDR, interfaces).

---

## 1. Problem Statement

The RDR knowledge-acquisition workflow forces experts to write discriminating conditions over a Case (any Python dataclass instance). In realistic cases the raw case attributes are insufficient — the expert must write new logic/equations (derived features) inline in a rule's condition. Consequences:

1. **Duplication:** a feature written for one rule is invisible to other rules; the same logic gets rewritten.
2. **Inefficiency:** identical or overlapping computations are re-evaluated per rule with no sharing.
3. **No abstraction layer:** RDR collapses Clancey-style *data abstraction* and *heuristic matching* into a single condition, unlike our OO code where features live as class helper methods/properties (SOLID).
4. **Case formulation ambiguity:** for structural domains (e.g., recognizing a Drawer in a kinematic world), it is unclear whether the case is the whole world, a candidate subtree (binary), or a multi-class discrimination input.
5. **Locality vs. sharing tension:** RDR's core guarantee (adding a rule never breaks existing rules, validated via cornerstone cases) is threatened the moment features/concepts are shared and editable.

## 2. Architecture (as converged in discussion)

### 2.1 Two-layer knowledge: Feature layer + Rule layer

- **Feature layer:** named, pure, reviewable Python — per-case-type feature modules or a `CaseView` wrapper with `@cached_property`-style memoized features, registered in a feature registry. Rules reference features **by name only**; no inline logic in conditions.
- **Rule layer:** EQL-based RDR conditions resolve attribute lookups against the feature registry first, then the raw dataclass.
- **KA workflow:** when the expert writes new logic in the IPython interface, the magic command captures it as a **named feature**, appends it to the feature module (same auto-serialization pipeline that already writes rule trees to source), and it becomes available to all future rules.
- **Dedup at capture time:** normalize the feature expression's AST, hash it, and compare against the registry; suggest existing near-duplicate features. Autocomplete over the registry in the IPython UI.
- **Efficiency:** one feature view per case per inference run; memoization = each feature computed once regardless of how many rules use it (a "poor man's Rete").

### 2.2 Concept trees (NRDR-style), layered on the existing GRDR fixpoint

The GRDR loop (re-evaluate all trees with new conclusions until fixpoint) already provides NRDR's *inference power*. What is missing is the *declaration half*:

- Allow a tree to be declared a **concept tree**: its conclusions are boolean/typed case attributes with proper names, explicitly marked as **vocabulary, not domain output**. Domain-output trees (e.g., Species, Habitat) remain distinct; a conclusion can be both (Species is legitimately both output and vocabulary).
- **Declared dependency graph:** record edges like `Habitat → Species` explicitly (extractable from which conclusions a tree's conditions reference). Used for:
  - **Stratified evaluation order** in the fixpoint loop (fewer passes).
  - **Refinement impact analysis:** when a concept tree (or shared feature) is edited, re-run cornerstone cases of all downstream trees; reject/flag the edit if any conclusion flips. This extends RDR's own cornerstone validation to the shared layer instead of importing a foreign discipline.
- **Refinement routing in the UX:** when a downstream rule misfires because an upstream conclusion was wrong, the interface should help the expert route the fix upstream (refine the Species tree once) rather than patching every consumer (duplication re-entering through the back door).
- **Monotonicity rule:** rules may only add conclusions, never retract another tree's output. This keeps the fixpoint convergent even under (rare) mutual dependencies (Habitat ↔ Species), i.e., non-stratified cases remain safe.

### 2.3 Datalog grounding (engine semantics)

- The GRDR fixpoint = Datalog **naive evaluation**; the dependency graph = **stratification**.
- Upgrade path: **semi-naive evaluation** — per pass, only re-fire trees whose referenced conclusions gained new facts in the previous pass. This is the principled scalability improvement over blanket re-evaluation.
- Optional later: JTMS-style **justification recording** per conclusion (which facts/conclusions it depended on) → incremental retract/recompute on world change + free "explanations" ("this is a Drawer because…").

### 2.4 OO integration: `definition` classmethods (Specification pattern)

- Each domain class may own a **definition RDR** (e.g., `Drawer.definition`) — necessary/sufficient-style recognition of candidates, colocated with the class; its serialized rule source lives beside the class; its cornerstone cases double as that class's regression tests.
- **Crucial constraint:** definitions must **not imperatively call** other definitions (`Drawer.definition` must not invoke `Handle.definition`). Instead, definitions *reference conclusions* ("subtree contains a body classified as Handle"), and the engine supplies them bottom-up per the dependency graph (inversion of control). This avoids hard-coded evaluation order, recomputation, and recursion on cyclic dependencies.
- Definitions are **pure**: `(candidate, scoped_view) → judgment (+ explanation)`; no mutation. Testable, cacheable.

### 2.5 Case formulation: hypothesize-and-test

Separate **generation** from **verification**:

- **Candidate generator per class:** a cheap, recall-oriented EQL structural query (e.g., "kinematic subtrees with a prismatic joint"). Deliberately over-generates; contains no expert judgment. Part of the class's recognition contract.
- **Definition (RDR) classifies candidates:** precision-oriented, judgment-laden, refinable by exception.
- **The case is `(candidate, context view)`** — the candidate subtree plus a *scoped* accessor into its neighborhood, not the whole world. The scoped view is the Law-of-Demeter boundary that keeps rule conditions local and maintainable.

### 2.6 Binary vs. multi-class: classify down the taxonomy

- **Exclusive siblings** (Drawer vs. Cabinet under Container): discriminate at the shared **parent** level — shared logic lives in the parent, exclusivity enforced exactly where siblings compete, adding a subclass touches only its parent's discriminator. Note the structural rhyme: SCRDR refinement-by-exception mirrors subclass specialization — the class hierarchy and rule tree become one structure.
- **Non-exclusive, cross-cutting concepts** (Openable, Graspable): independent binary definitions — mixins, in OO terms.

## 3. Repo Mapping (to be verified by code exploration)

| Proposal | Expected home |
|---|---|
| Feature registry / CaseView / memoization | new module in `krrood/entity_query_language/eql_rdr` (or `eql` core if attribute resolution hooks live there) |
| Feature capture + AST-dedup in KA flow | eql_rdr IPython interface (magic commands) |
| Concept-tree declaration, dependency graph, stratified/semi-naive fixpoint | eql_rdr engine — **note:** GRDR/MCRDR exist only in legacy `krrood/ripple_down_rules`; the new eql_rdr currently has SCRDR only, so MCRDR/GRDR porting is a prerequisite for this layer |
| Cornerstone regression on feature/concept edits | wherever cornerstone cases are stored/validated in eql_rdr |
| `definition` classmethods + candidate generators | domain-model side, consuming eql_rdr API; serialization piggybacks on existing rules-to-source pipeline |

## 4. Phased Plan (proposal — refine against code)

1. **Phase 0 — Grounding:** explore `eql` and `eql_rdr`; map how conditions are represented (AST availability?), how rule trees serialize to source, how cornerstone cases are stored, how the IPython magics capture expert input. Compare against legacy `ripple_down_rules` for MCRDR/GRDR design worth porting.
2. **Phase 1 — Feature layer:** feature registry + CaseView memoization + name-resolution in EQL conditions + IPython capture of named features + AST-hash dedup + registry autocomplete.
3. **Phase 2 — MCRDR + GRDR in eql_rdr:** port/redesign from legacy, but with the dependency graph and monotonic-conclusions contract designed in from the start.
4. **Phase 3 — Concept trees + safety net:** concept declaration, dependency edges, stratified order, semi-naive firing, cornerstone-regression check on feature/concept edits, upstream-fix routing in the UI.
5. **Phase 4 — OO integration:** `definition` classmethod protocol, candidate-generator protocol, `(candidate, scoped view)` case type, taxonomy-level discriminators.
6. **Phase 5 (optional/later):** justification recording (TMS) for incremental world updates and explanations.

## 5. Open Questions (decide during grounding)

- Where should feature resolution hook in: EQL's attribute access layer, or an eql_rdr-specific case wrapper?
- Feature versioning vs. cornerstone-gated editing (we leaned toward the latter; versioning as fallback for breaking edits)?
- Are concept-tree conclusions written into the case (derived-attribute namespace) or held in an engine-side blackboard? (Blackboard keeps dataclasses clean; namespace is simpler for EQL conditions.)
- Cycle policy: detect-and-warn on dependency cycles, relying on monotonic fixpoint? Or forbid cycles initially?
- How do generators get registered/discovered per class (decorator, classmethod, entry in a registry)?
- Migration story: does anything in legacy `ripple_down_rules` (interfaces, tree types) constrain the new API for backward compatibility, or is eql_rdr free to diverge?

## 6. Literature Anchors

- **NRDR** — Beydoun & Hoffmann: expert-defined named concepts, each an RDR tree; concept refinement fixes all consumers at once; requires consistency checking on shared-concept edits.
- **MCRDR with repeated inference / cascaded RDR** — Compton et al.: conclusions fed back as case attributes (= our GRDR loop).
- **Heuristic classification** — Clancey 1985: separate data-abstraction layer from matching layer.
- **Datalog**: naive/semi-naive evaluation, stratification — the principled semantics for the GRDR engine.
- **Rete** — Forgy: shared condition evaluation; approximated here by feature memoization.
- **JTMS** — Doyle: justification-based truth maintenance for incremental updates and explanations.
- **Specification pattern** — Evans/Fowler (DDD): recognizer separated from (but colocated with) the domain object.
- **Hypothesize-and-test / blackboard** — Hearsay-II; candidate generation as in DeepDive-style pipelines.
- **Description logics** (KL-ONE/OWL): class-as-definition, subsumption-based classification down a taxonomy.

## 7. Suggested First Prompts for the Coding Session

1. "Read `docs/rdr_architecture_plan.md`. Then explore `krrood/entity_query_language` (especially `eql_rdr`) and `krrood/ripple_down_rules`. For each item in Section 3, report what already exists, what conflicts, and what's missing. Do not write code yet — produce a grounded implementation plan for Phase 1."
2. "Show me how a rule condition is currently represented and serialized in eql_rdr, and whether we have access to its AST at capture time (needed for feature extraction and dedup)."
3. "Compare the legacy MCRDR/GRDR implementations with eql_rdr's SCRDR design and propose how MCRDR/GRDR should look in the new architecture with the dependency graph built in."
