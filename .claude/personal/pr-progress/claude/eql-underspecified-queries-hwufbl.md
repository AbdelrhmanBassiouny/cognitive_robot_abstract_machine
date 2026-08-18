## EQL underspecified queries (montessori-eql-stack item `montessori_underspecified_queries`)

Branch `claude/eql-underspecified-queries-hwufbl`, based on `cramera_eql_autocomplete`
(#170), which is what makes any workspace class nameable in a query - the feature needs
that to name an action class in the console.

### Plan
1. cramera: `QueryScope.UNDERSPECIFIED` (heading "Underspecified Queries"),
   `GenerativeEvaluation` answering a match through krrood's
   `EntityQueryLanguageGenerativeBackend`, and `QueryEvaluation.names()` so the
   evaluation puts `generate` in reach of the next question.
2. cramera row rendering: an enum member reads as its member name, and an instance a
   query built (which names nothing of its own) is rendered as its fields alone rather
   than as its `repr`.
3. montessori demo: an `UNDERSPECIFIED` body of knowledge over the live shapes and the
   board, three presets around `an(InsertMontessoriShapeAction)(..., arm=...)`, and the
   board wired into the query source from `_attach_cramera`.
4. Tests: `test/cramera_test/test_generative_evaluation.py` (mimic records with enum
   fields) and a new class in `test/experiments_test/test_montessori_live_query.py`.

### Done
- All four steps implemented on the branch.

### Next
- Run the cramera + experiments suites in this container, open the draft PR, record the
  item in the plan manifest, republish the dashboard.
