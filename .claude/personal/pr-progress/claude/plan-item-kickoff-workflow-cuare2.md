# bastler-package — PR #185 (draft), branch `claude/plan-item-kickoff-workflow-cuare2`

Plan `workflow-unification`, track `bastler`, wave `upstream`. Based on fork `main`
(`90c24116`). Kicked off in session
https://claude.ai/code/session_01JN9p5Kf2DKtzryspPX2KqZ.

Create the `bastler` package and move every Python module under `.claude/` into it, so the
three separate `sys.path` roots stop preventing any shared definition from existing. Full
rationale in the plan's `roadmap.md` under the 2026-08-20 kickoff entry.

## Scope, settled with the user at kickoff

- **Pure move.** ~18,408 lines / 46 modules, via `git mv` so GitHub renders renames.
  `stack.py` (1,641), `plan_item_bootstrap.py` (1,612) and `build_dashboard.py` (1,504) keep
  their shape — splitting them becomes its own item once the package exists.
- **Only straight-deletion unifications**: one `ItemStatus`, and `stack.py`'s second Python
  copy of the notes-branch precedence. The `git_interface.py` seam and the command-class base
  stay with `bastler-notes-core-python` and their own items, because #135's
  `check_scope_overlap.py` and #151's `Subcommand` are not on `main`.
- Flat package layout — fixed by #111's `development_tooling/` and by decision 12's flat
  module names for the seven conversion items.

## Done

- [x] Dependencies re-checked live (`check_dependency_readiness.py`): #101 and #106 both
      `merged`, both `is_ready`.
- [x] Branch created off `main`, bootstrap commit `63ac83de3` pushed.
- [x] Draft PR #185 opened (by the session's GitHub tool, so it is attributed to the user
      rather than `claude[bot]`).
- [x] `plan_item_bootstrap.py open` + `record`: `branch`, `session`,
      `pull_request_number: 185`, `status: in_progress`, roadmap section appended. Verified by
      re-reading the manifest off the notes branch.

## Next — in order, each commit green

1. **Skeleton + contract tests, failing first.** `bastler/__init__.py`,
   `bastler/pyproject.toml` (mirroring #111's, `[tool.setuptools.package-dir] bastler = "."`),
   `test/bastler_test/{__init__,conftest}.py`. Five tests: zero-install import from the repo
   root; every module imports in its own subprocess (the shape
   `test_every_module_of_the_executor_imports_on_its_own` already uses — catches cycles a
   single-entry-point suite hides); `python -m bastler.<x> --help` for every entry point; the
   hook-reachable modules import with third-party modules blocked (decision 12 tier 1); no
   Python remains under `.claude/`.
2. **Move `.claude/stack/`** (14 modules + suite). First, because its conftest is the one
   already reaching into the other two directories.
3. **Move `.claude/skills/plan-dashboard/`** Python + `templates/` (it is resolved as
   `Path(__file__).parent / "templates"` in `render_common.py:22`, so it moves with the module
   that loads it). `example/` stays — it is a documentation asset of
   `example-walkthrough.md`; only the tests' path to it changes.
4. **Move `.claude/hooks/`** Python + test helpers + `tests/fixtures/`.
5. **The two unifications**, plus deleting the test that held the two `ItemStatus` copies
   equal — it guards a duplication that no longer exists.
6. **Entry points, CI, documents.** Bash callers → `python3 -m bastler.<module>`;
   `resolve-personal-notes-config.sh` constants repointed and the three test-directory
   constants collapsed into one; `ci.yml` job → `test_bastler` with `--confcutdir`; the 15
   documents naming a moved path; `scripts/format_docstrings.py` on every touched file.

## Verification

622 tests across the three current directories must not drop, through the single new
invocation `python -m pytest test/bastler_test --confcutdir=test/bastler_test`. Every new test
mutation-checked. Live: `check-setup.sh` exits 0, `save-plan.sh` round-trips against the real
notes branch, `refresh_dashboard.sh` renders this plan's dashboard, `stack.py configuration`
answers. Zero-install proven from a clean clone of the pushed branch (#121's staged-diff
lesson), plus `pip install ./bastler`.

## Open / carried

- **Not subscribed to tracking issue #102** — the call was refused by the permission
  classifier. Concurrent structural changes reach this session only via the delta recheck
  (`plan-updates-since.sh workflow-unification --since ee517e49`), not via events.
- **CI job rename** changes the reported check name; if `test_claude_dev_tooling` is a required
  status check, branch protection needs updating. Flagged to the user, not acted on.
- **To tell on their own pull requests before this lands**: #158 (`pin-tooling` copies
  `.claude/stack/`, which becomes empty) and #111 (folds its modules in under the `bastler`
  name). Not yet done.
- Re-draft after every push, per the standing rule.
