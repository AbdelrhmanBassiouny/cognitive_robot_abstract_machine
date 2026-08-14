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

5. `NoDAOFoundError` when running the notebook on a fresh clone: the tracked
   `ormatic_interface.py` files are empty, so no DAO exists until
   `scripts/regenerate_all_orm.py` has run (~52s). Moved that logic out of the
   script into the installed meta-package
   (`cognitive_robot_abstract_machine/orm_interfaces.py`: `OrmInterface`,
   `WorkspaceOrmInterfaces`, `WORKSPACE_ORM_INTERFACES`, plus
   `exceptions.py`); both `scripts/regenerate_all_orm.py` and
   `scripts/protect_generated_orm_interfaces.py` are thin CLIs over it. The
   notebook's new first cell regenerates only when `are_generated` is False.
   New tests `test/cognitive_robot_abstract_machine_test` (8, wired into the
   CI matrix as `lib: cognitive_robot_abstract_machine`), README section.

6. `DetachedInstanceError` from the notebook's last cell
   (`queried_plan[0].from_dao()`): `SQLAlchemyBackend._evaluate` opened a
   session per evaluation that only the generator frame held, so it was
   garbage collected with the generator and detached every returned DAO. The
   backend now owns one session (`session: Session = field(init=False)` set in
   `__post_init__`), so results stay usable as long as the backend does. Test:
   `test_backends.test_result_of_a_sqlalchemy_query_can_be_converted_back`.

Both fixes are committed and pushed to `origin/icjai-tutorial` (d65ec42442,
49b7744807). Pre-existing unrelated failure on this branch:
`test_random_events_translator.test_comparison_between_two_variables_is_refused`
(fails with all my changes stashed too).

Next: nothing outstanding; user has not asked for a PR.
