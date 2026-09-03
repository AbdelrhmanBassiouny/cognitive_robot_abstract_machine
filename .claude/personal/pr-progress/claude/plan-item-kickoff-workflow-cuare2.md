## PR #185 - bastler package extraction

Resolving what stalled it, per `/plan-item-resolve bastler-package bastler-package`
(auto mode). The pull request itself was finished and approved: out of draft since
2026-08-23, CI green, both original dependencies merged. What held it was the
`needs-resolution` label, which withholds a branch from promotion, live since
2026-08-22 and re-reported by the maintenance routine ~20 times between 2026-08-31
and 2026-09-03.

### The conflict, and its silent half

- `.claude/hooks/tests/test_setup_steps.py` was added on `main` inside a directory
  this branch renamed. Git reports `CONFLICT (file location)` and will not place it.
  That is the one file every routine comment since 2026-08-31 names.
- `.claude/hooks/setup_steps.py` (626 lines) landed on `main` too and merges with
  **no conflict at all**, because this branch moved `.claude/hooks/*.py` file by file
  rather than renaming that directory. Left where it lands it breaks this branch's own
  `test_no_python_module_remains_under_the_claude_directory`. Third occurrence of the
  hazard the pull request body already names twice.

Both arrive from `bastler-first-time-setup`, which landed as upstream #577 (`017be2aa2`)
on 2026-09-01 while the manifest still called it `in_progress`.

### Done

- Merged `origin/main`; placed the new suite at `test/bastler_test/test_setup_steps.py`.
- `git mv .claude/hooks/setup_steps.py bastler/setup_steps.py`; its `PROJECT_ROOT`
  hand-counted `.parent` chain becomes `bastler.package_layout.REPOSITORY_ROOT`, and its
  usage line becomes `python3 -m bastler.setup_steps`.
- Repointed `.claude/SETUP.md` and `.claude/hooks/README.md` at the module's new home.
- Converted the moved suite off the `sys.path` hackery this branch deletes: package
  imports, relative imports of the shared test modules, `PythonModuleRunner` +
  `install_package()` in place of a hand-built `subprocess.run`.
- Recorded the real blocker in `plan.yaml`/`roadmap.md` before starting, and corrected
  `bastler-first-time-setup` to `done`.

### Next

- Push, update the pull request description (entry-point count, test count, the third
  merge, #203 having landed), republish the dashboard, clear `needs-resolution`.
- Leave the pull request **ready, not draft**: the un-draft is this workflow's promotion
  approval, and re-drafting would withdraw it.
- Two review threads stay open on purpose; both are the user's to close.
