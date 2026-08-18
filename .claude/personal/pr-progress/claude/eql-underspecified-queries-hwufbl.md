## EQL underspecified queries — draft #180 (plan item `montessori_underspecified_queries`)

Branch `claude/eql-underspecified-queries-hwufbl`, based on `cramera_eql_autocomplete`
(#170), which is what makes any workspace class nameable in a query — the feature needs
that to name an action class in the console. Tracked in plan `montessori-eql-stack`,
new track `underspecified-queries`; structural change recorded on tracking issue #174.

### What shipped (two commits, a6478a3e + 17e94bb4)
1. cramera: `QueryScope.UNDERSPECIFIED` ("Underspecified Queries"), a
   `GenerativeEvaluation` over krrood's `EntityQueryLanguageGenerativeBackend`, and
   `QueryEvaluation.names()` so the evaluation puts `generate` in reach of a follow-up
   question. `EqlQueryRunner.names` merges it with the source's `extra_names`; the
   bridge builds one runner for both running a query and advertising its vocabulary.
2. cramera row rendering: an enum member reads as its member name unless its value is
   already text; an instance a query built (naming nothing of its own) renders as its
   fields alone rather than titled by its `repr`.
3. montessori demo: an `UNDERSPECIFIED` body of knowledge over the live shapes and the
   board, three presets around `an(InsertMontessoriShapeAction)(..., arm=...)`, and the
   board wired in from `_attach_cramera`.
4. Tests: `test/cramera_test/test_generative_evaluation.py` (9) and
   `TestWhatTheDemoCouldDo` in `test/experiments_test/test_montessori_live_query.py`.
   No frontend change was needed — `preset_groups.js` and the `/presets` scopes payload
   were already generic.

### Test state
`pytest test/cramera_test` 486 passed; `test_montessori_live_query.py` 19 passed. The
rest of `test/experiments_test` needs generated ORM interfaces and a ROS install this
container has neither of — left to CI.

### This container, if a later session lands in it
The repo needs Python ≥3.12 (`type X[T] = ...` in coraplex, `make_dataclass(module=)`
in the conftest's class diagram) and the image ships 3.11: there is a working 3.12
virtualenv at `/home/user/venv312` with the whole workspace installed editable, plus
`ros_stub.py` in the session scratchpad (a pytest plugin fabricating rclpy and the ROS
message packages) — run experiments tests as
`PYTHONPATH=<scratchpad> venv312/bin/python -m pytest ... --noconftest -p ros_stub`.
`cramera/scenes` had to be `git submodule update --init`ed for the bundle-preset test.

### Next
Nothing outstanding in this session. CI on #180 is unseen; per my notes the PR is not
watched, so any red job or review comment comes back as a fresh prompt.
