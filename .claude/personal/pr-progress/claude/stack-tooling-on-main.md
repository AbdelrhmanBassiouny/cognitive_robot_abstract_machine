# PR #106 - stack tooling on main (`claude/stack-tooling-on-main`)

Plan item: `workflow-unification` / `stack-tooling-on-main`. Open and ready (the user
marked it ready for review 2026-08-03), based on `main`.

## Done

- **`e20b0bb4`** - the maintenance pass became `/stacked-pr-maintenance`; four `stack.py`
  subcommands (`labels`, `preflight`, `promotion-link`, `reparents`/`landed`) plus
  `configuration --fork/--upstream`.
- **`8b7435bb`** - the 25-comment review round, all applied. Three were user decisions:
  drop label-and-close because GitHub already marks a pull request merged when its head
  becomes an ancestor of its base (proven from #101/#103/#105); the skill never writes
  code, which incidentally made it repo-generic; delete `POINTER.md`, `prompt_model.py`
  and 18 of the 19 prose tests. 313 tests pass.
- **`65884bd44`** - both `routine-prompt.md` sections the user asked to drop, plus the
  `README.md` sentence advertising one of them. 29 lines left.
- **Split settled (user decision)**: `stack.py` is not split here;
  `dev-tooling-python-package` does the surgery once, when it moves every `.claude/`
  Python file into the package. Replied on the thread, left it open.
- **#110's rebase instructions rewritten** and posted on that PR: the review round
  deleted the artifacts three of the five points referred to. Found one real defect while
  checking - `check-stack-setup.sh` requires `ROUTINE.md` and `routine-prompt.md`, so it
  reports `needs-setup` on a correctly installed checkout after the rebase.
- Description rewritten twice, manifest + roadmap saved, dashboard republished, every
  thread answered.

## Next

- Waiting on review. Nothing blocking.
- **Flagged, needs a decision**: the HARD RULES no longer bind before the first file is
  read now that the pointer is gone - that reverses design decision 4. Say if the three
  rules should stay in the registered prompt.
- Due when this lands: register the routine prompt as a `/stacked-pr-maintenance` call
  with `fork=`, `upstream=` and `--non-interactive`.
- Still #110's: deleting the ~120-line remote inference alongside the setup that writes
  `fork_repository`. `stack.toml:23` and `stack.py:84` stay open for it.
- Do not re-draft unless a new commit is pushed - the user marked this ready deliberately
  (and #123 proposes exactly that rule).
