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

## Outstanding
- CI on #501 not yet observed (not polled, by the user's rule).
- Landing: #420/#424/#430/#437/#107 merge across the second move.
- Pre-existing, recorded only: xdist race on board.json; add-plan-item/SKILL.md uses undefined
  ${PLAN_ITEM_BOOTSTRAP_SCRIPT}.

## Next
- Waiting for the user's review of draft #501.
