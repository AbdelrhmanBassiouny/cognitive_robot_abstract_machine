Branch `icjai-tutorial` (no PR opened). Work: four EQL verbalization fixes
found while reviewing `experiments/src/ijcai_demo.ipynb`.

Plan / status (all done, tests green: `test/krrood_test/test_eql`, 1194 passed):
1. Disjunction nesting - `OrRule` now emits a `BlockFragment` headed by
   *"either"*, so `OR(AND(A,B), AND(C,D))` is a level in the hierarchical
   outline with one point per AND (user chose "either" + AND-stays-one-point).
   New test: `test_verbalization/test_disjunction_nesting.py`.
2. `the(<Type>)` as a Match read "a X" - `MatchPlan` now carries `is_unique`
   /`selected_type` and the match assembler renders "the unique X" through the
   shared `SelectionAssembler.unique` (also used by the query assembler;
   `QueryPlan.is_the` renamed to `is_unique`).
3. Floats round to 3 decimals in `value_lexicon.value_phrase`
   (`FLOAT_DISPLAY_DECIMALS`).
4. `VerbalizationPipeline.display` now takes `services`/`backend` and shares a
   new public `build()` with `verbalize`.

Also updated: `krrood/doc/eql/user/verbalization.md` (either-block, the-unique
match, new hierarchical example).

Notebook TODOs: all `# TODO` cells are `exercise`-tagged stubs each paired with
a `hide-cell`/`example-solution` cell - intentional, nothing to fix.

Next: nothing outstanding; user has not asked for a PR.
