# Project Rules

## Generated ORM Interfaces
- `ormatic_interface.py` files are generated, never written, and git-ignored (see `.gitignore`). Never edit them, and never read them to debug an ORM problem; regenerate them with `scripts/regenerate_all_orm.py` instead
- The test suite builds them for its runs; a local checkout builds them with `scripts/regenerate_all_orm.py`
- Never track one again: git refuses to overwrite a tracked path a checkout has generated its own copy of, which makes every branch switch fail
- When regenerating the ORM interfaces does not fix an ORM problem, ask the developer
- If an ORM import creates an import cycle, ask the user if a local import is fine

## Running Tests
- Pass `--orm-build never`, and regenerate the ORM interfaces explicitly with `scripts/regenerate_all_orm.py` when a change needs it

## krrood Isolation
- `krrood`, including its tests under `test/krrood_test`, never imports another workspace package - in particular not `coraplex`, `semantic_digital_twin`, `giskardpy`, `physics_simulators`, `robokudo` or `experiments`. The only exceptions are `random_events` and `probabilistic_model`, which `krrood`'s source already depends on
- When a `krrood` test needs behaviour another package triggers, mimic the relevant classes and patterns in `test/krrood_test/dataset` and test against the mimics. Keep the test in `krrood` and do not depend on another package to reproduce the scenario
- Those mimic classes import only `krrood`, `random_events` and `probabilistic_model`

## Domain-Specific Conventions
- For spatial types and connections, follow `semantic_digital_twin/doc/style_guide.md`
- A path enum derives from `basstler.locations.PathEnumeration` instead of repeating its `with_segments` and `__hash__` overrides
