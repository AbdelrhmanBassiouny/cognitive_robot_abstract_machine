# eql-verbalization — standing rules

- Operand naming: grammatical metadata on the field → field/attribute name → type name (last resort). Provide the metadata mechanism with good defaults (low modelling burden); build on the existing `_attribute_name_` / possessive / referring microplanning. (Replaces "always the type name", which read awkwardly, e.g. "Point3".)
- Same-type operands: determiners ("a point … the other point"), not numbering ("Point3 1/2").
- Value-agnostic (first-order) + value-using forms, and abstract→concrete-subclass expansion ("a Body or a Region"): their own phase (P3), on `concrete_subclasses` + `RoleFragment.for_type` / `for_literal`.
- Fragments must use `Noun` / `Noun.bare` / `Noun.the`, never a raw `WordFragment`.
- `EuclideanPlanarDistance`: `custom_relation` with `Prepositions.BETWEEN`, not `of`.
- `Pose` type hints (predicates.py:292, robot_predicates.py:158 are HomogeneousTransformationMatrix): investigate and switch to `Pose` if correct/clearer.
- No abbreviations (`cm`→`collision_manager`); sweep all touched code.
- Keep the functional wrapper name `get_volume` (the class stays `AnnotationVolume`).
- ormatic `type`-mappability PR: DROPPED (maintainer), so excluding `SymbolicCallable` subclasses from ORM generation is the surviving path for P4's `ClassNameLowercased`. Superseded 2026-07-30: `OPERAND_OVERRIDES` no longer exists — P3 replaced it with the `SymbolicCallable._example_operand_values_` class hook, which the snapshot consults per class.
- Keep surfaces concise (omit root/tip from `BlockingBodies`); details are query-able.
- `Reachable` reads *"a Pose is reachable for the kinematic chain rooted at `<root>` and ending at `<tip>`"* — the chain is what reaches, and root/tip stay named here (unlike `BlockingBodies` under decision 10) because reachability is only meaningful relative to them.
- Naming a referent by value *and* type on first mention (*"a gripper of type HasTwoFingers"*) is out of P4's scope — it is coreference behaviour, not an sdt wording, and is tracked as its own item (`p5-first-mention-type-annotation`).
