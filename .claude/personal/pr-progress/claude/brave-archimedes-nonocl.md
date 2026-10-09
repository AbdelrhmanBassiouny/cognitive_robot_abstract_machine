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
- Branch re-cut from main, draft PR #501, manifest open+record, roadmap section written.
- b931f268f src layout (716 pass). f90378beb environment + BASSTLER_PYTHON (727 pass).
  Live: session-start created basstler/.venv via uv (3.13), second start "already installed".
- Decisions: installer is `pip --python <venv python> install --editable ./basstler` (venvs made
  --without-pip / by uv); ScriptRunner's PythonModuleRunner puts <root>/basstler/src on PYTHONPATH;
  check-setup + save-plan no longer read an unparseable declaration as "nothing missing" (new tests).
- No BASSTLER_PYTHON env override (YAGNI): venv if present, else python3.

## Next
- Step 4: requires-python >=3.12 (pyproject + BASSTLER_PYTHON_REQUIREMENT), upstream-reviews.yml 3.12,
  PathEnumeration(Path, ReprEnum); watch `ids=lambda member: member.name` in tests (Path.name shadows).
