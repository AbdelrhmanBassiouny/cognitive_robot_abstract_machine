## Plan
- Declare core (import-linter forbidden contract + [tool.krrood.core-boundary]) in krrood/pyproject.toml.
- Runtime test: every core module in a fresh -X importtime interpreter; allowed = stdlib + krrood + transitive core deps; offender list exact.
- Static test: run the import-linter contract; offending edges in ignore_imports.
- Add import-linter to krrood's dev extra.

## Done
- Branch, draft PR #546, plan item recorded in progress.

## Next
- Set up a uv environment, measure today's offenders, write tests first.
