Plan
- Scope the integration branch to tooling + bug fixes (stack.toml integration_scope_labels / tooling_paths / shared_paths).

Done
- 54b8d8cdd4 on integration's .claude/stack: IntegrationScope, BranchChanges, OUT_OF_SCOPE; 1074 tooling tests pass.

Next
- User decides how it lands: fast-forward integration to this branch (stopgap precedent 5a5097f4ef) or a PR; no PR opened since integration is not a PR base.
- Port the same scope into the bastler/basstler chain (#293 only filters by the tooling label, opt-in).
