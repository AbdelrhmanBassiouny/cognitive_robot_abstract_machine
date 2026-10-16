# actions-budget — standing rules

- Draft pull requests run the changed libraries plus their dependents. The full matrix runs on ready for review, a `full-ci` label or dispatch.
- The integration pipeline is event-only: no `schedule` anywhere.
- Plan it here, take the fastest route to unblocking, and keep it clean. Prevent a repeat, and add monitors and warnings that fire when rates are being exceeded.

## changed-library-matrix — settled plan (2026-10-16)

- Draft pull request pushes run the matrix libraries whose package or test directory a change touches, plus every library depending on them (each package's own `pyproject.toml`). Tooling- or docs-only changes run the tooling job alone; any other path runs everything.
- `ci.yml`'s matrix is one `lib` axis with a run-time `exclude`; basstler counts such a matrix by its static axes, so it stays countable.
- Decided with the user: `ci.yml`'s `jobs_per_push_run` override stays at 16. That is the worst case (a change to `krrood`, which every library depends on), so the item's note to drop it does not hold at the default of 4.
- #284's classifier has not landed; converge with it when the second lands.
