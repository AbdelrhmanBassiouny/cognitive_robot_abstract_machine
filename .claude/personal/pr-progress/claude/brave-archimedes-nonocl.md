# basstler-src-layout - PR #501 (plan basstler-package)

Based on main, since #185 merged on 2026-10-05. Auto mode. Baseline: 710 tests pass (py3.13).

## Plan
1. [x] src layout: git mv modules + templates/ queries/ stack.toml plan-item-modes.toml to basstler/src/basstler/.
   pyproject: packages.find where=src, no package-dir ".", pyproject.toml no longer package data.
   PackageLocation: distribution directory, REPOSITORY_ROOT counted from it, DEPENDENCY_DECLARATION read from source.
   Contract test: no *.py directly under basstler/. sync_version + version tests. CI installs `-e ./basstler`.
2. [x] basstler/.venv (gitignored), created by session-start from 3.12+ (uv preferred, else python3.1x -m venv),
   with `./basstler` installed editable. dependencies module also reports basstler itself when it is not installed.
3. [x] BASSTLER_PYTHON (inherited value > venv > python3) + PYTHONPATH=basstler/src exported in resolve-personal-notes-config.sh;
   replace python3 -m in hooks / SKILL.md / READMEs / workflows. ScriptRunner passes BASSTLER_PYTHON=sys.executable.
4. [ ] requires-python >=3.12, workflows to 3.12, PathEnumeration(Path, ReprEnum) with with_segments + __hash__.
5. [ ] Format docstrings, run the full suite, update the PR description, refresh the dashboard.

## Done
- All five steps. Commits: b931f268f src layout, f90378beb environment + BASSTLER_PYTHON,
  e3228ac42 3.12 + PathEnumeration(Path, ReprEnum), 5eb.. docstring format, ff522d414 board copy + workflow.
- 745 pass on 3.12 (scratchpad py312 uv venv) and 3.13. Live session-start created basstler/.venv via uv.
- PR description rewritten to the final state; roadmap section "implemented on #501" recorded.
- Decisions: `pip --python <venv> install --editable ./basstler`; dependencies module counts the package
  itself; PYTHONPATH=basstler/src exported; member names via `_name_`.

## Round two (2026-10-12, the user asked to fix the three recorded items)
- 174d88f5e MaintenancePass carries its board; autouse board fixture deleted (xdist race gone).
- 79360e121 add-plan-item uses PLAN_ITEM_BOOTSTRAP_MODULE; contract test on every ${NAME} in .claude docs.
- 8a08808f0 3.11-only machine: pip install --target basstler/.uv uv, then uv fetches; uv venv --no-project;
  uv pip install whenever a uv exists (system pip 24.0 broke on a uv-fetched 3.15).
- 750 pass on 3.12 (serial and -n), 3.13, 3.15. PR description, roadmap section updated.

## Round three (2026-10-12, fork review, 9 threads)
- 1d3674cfd: prs -> pull_requests in stack.py; version classifiers dropped; test enums EnvironmentVariable,
  StubVariable, PackageManager, GitHubClient, FileMode, SummaryLine; ProjectDeclaration dataclass for
  [project] tables; check-setup declaration as dataset file. 750 pass on 3.12 and 3.13.
- All 9 threads replied and resolved. PathEnumeration -> krrood.patterns recorded in plan (af80c15e0).

## Round four (2026-10-12, one thread on constants.py:316: enums in source?)
- b8f5d565d: ClaudeCodeVariable -> basstler.locations (plan_item_bootstrap/mode read it);
  GitHubClient -> basstler.maintenance_constants (upstream_reviews gh default);
  ScratchBranch.PERSONAL_NOTES = PersonalNotesSetting.BRANCH.default. 750 pass on 3.12/3.13.
- Replied; thread left OPEN (PackageManager etc. kept in tests: no Python reader). StackLabel waits on #107.

## Outstanding
- Thread on constants.py:316 open for the user.
- CI on #501 not yet observed.
- Landing: #420/#424/#430/#437/#107 merge across the second move.
- Open: uv picks the newest interpreter (3.15 here) while CI tests 3.12.

## Next
- Waiting for the user's review of draft #501.
