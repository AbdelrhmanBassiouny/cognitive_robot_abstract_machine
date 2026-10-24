PR #529 (draft, base main): cache SubClassSafeGeneric.get_type_of_generic_parameter per class and parameter. Not a plan item.

Plan
- lru_cache on the classmethod; tests prove the second read skips resolution and siblings keep their own binding.

Done
- Pushed 1 commit: lookup 924 -> 123 ns, krrspatial point subtraction 1411 -> 845 ns. krrood patterns/eql/ormatic/utils/bounds pass.

Next
- Wait for review and CI; promote upstream via a promotion link when the user asks.
