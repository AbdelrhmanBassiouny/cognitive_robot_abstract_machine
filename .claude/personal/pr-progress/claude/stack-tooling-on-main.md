# PR #106 - stack tooling on main (`claude/stack-tooling-on-main`)

Plan item: `workflow-unification` / `stack-tooling-on-main`. Draft, based on `main`.

## Done

- **`e20b0bb4`** - the maintenance pass became `/stacked-pr-maintenance`; four `stack.py`
  subcommands (`labels`, `preflight`, `promotion-link`, `reparents`/`landed`) plus
  `configuration --fork/--upstream`.
- **`8b7435bb`** - the 25-comment review round, all applied. Three were user decisions:
  drop label-and-close because GitHub already marks a pull request merged when its head
  becomes an ancestor of its base (proven from #101/#103/#105); the skill never writes
  code, which incidentally made it repo-generic; delete `POINTER.md`, `prompt_model.py`
  and 18 of the 19 prose tests. 313 tests pass.
- Description rewritten twice, PR back to draft, manifest + roadmap saved, dashboard
  republished, every thread answered.

## Next

- Waiting on review. Nothing blocking.
- **Open question put to the user on the PR**: splitting `stack.py` (~1,540 lines). My
  recommendation is to let `dev-tooling-python-package` do it once rather than twice.
- **Flagged, needs a decision**: the HARD RULES no longer bind before the first file is
  read now that the pointer is gone - that reverses design decision 4. Say if the three
  rules should stay in the registered prompt.
- Due when this lands: register the routine prompt as a `/stacked-pr-maintenance` call
  with `fork=`, `upstream=` and `--non-interactive`.
- Still #110's: deleting the ~120-line remote inference alongside the setup that writes
  `fork_repository`. `stack.toml:23` and `stack.py:84` stay open for it.
