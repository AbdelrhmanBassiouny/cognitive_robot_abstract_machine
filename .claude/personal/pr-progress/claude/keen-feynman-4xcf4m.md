## Plan
- Core declared in krrood/pyproject.toml (import-linter contract + [tool.krrood.core-boundary]); runtime + static guards with shrinking offender lists.

## Done
- Declaration, 4 tests (198 pass locally, mutation-checked), import-linter in workspace dev extra; PR #546 description current.

## Next
- Check CI: the offender list was measured in a krrood-only env; adjust once if the full workspace env differs.
