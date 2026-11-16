Plan
- Keep #66 mergeable against `main` and carried into the stack above it.

Done
- 2026-11-16: merged `main` (`97fcca43a9`) into the branch (`d7b3499c2f`) and pushed. It conflicted in `dataclass_source.py`, `ormatic/utils.py` and `patterns/classproperty.py`, because `main` had made the same `classproperty` move. Merge probe afterwards: clean.
- Tests at `d7b3499c2f`: `test_eql_rdr`, `test_code_generation`, `test_patterns` (347), `test_eql/test_core` (424), `test_ormatic` (262) pass; `krrood check` passes on the touched files.
- All 77 review threads are resolved. Description updated.

Next
- Read CI on `d7b3499c2f` (not read yet).
- Read upstream review state: the upstream-reviews Action's reader crashed (a KeyError on `error`).
- Restack the descendants onto `d7b3499c2f`: `maintenance restack --stacked-on D-core-serialization` fails at the `D-ui-rendering` checkout.
- Owner: remove the `integration-conflict` label; ask whether the item is finished (PR is out of draft, promotion unknown).
