# bastler-package — PR #185 (draft), branch `claude/plan-item-kickoff-workflow-cuare2`

Plan `workflow-unification`, track `bastler`, wave `upstream`. Based on fork `main`
(`90c24116`). Kicked off and implemented in session
https://claude.ai/code/session_01JN9p5Kf2DKtzryspPX2KqZ.

Create the `bastler` package and move every Python module under `.claude/` into it, so the
three separate `sys.path` roots stop preventing any shared definition from existing. Full
rationale in the plan's `roadmap.md` under the 2026-08-20 kickoff and 2026-08-21 implementation
entries.

## Scope, settled with the user at kickoff

- **Pure move.** 46 modules via `git mv`; 68 changed files render as renames. `stack.py`
  (1,641), `plan_item_bootstrap.py` (1,612) and `build_dashboard.py` (1,504) keep their
  shape — splitting them becomes its own item once the package exists.
- **Only straight-deletion unifications**: one `ItemStatus`, and `stack.py`'s second Python
  copy of the notes-branch precedence. The `git_interface.py` seam and the command-class base
  stay with their own items, because #135's `check_scope_overlap.py` and #151's `Subcommand`
  are not on `main`.
- Flat package layout.

## Done — everything the plan listed

- [x] Skeleton, `pyproject.toml`, and 58 contract tests (`39bc17c27`).
- [x] The move, the import rewrites, the entry points, CI and the documents — one commit
      (`a4405fbd5`), because `scratch_repository.py` is shared by two of the three suites, so
      splitting it per directory would have needed the `sys.path` bridge this deletes.
- [x] Package data for an installed copy (`a826533b4`), found by running `pip install ./bastler`
      and watching it import and then fail at the first render.
- [x] **536 tests pass** = 479 on `main` + 58 new − 1 deleted (the executor's per-module import
      test, superseded by the contract suite covering all 24 modules).
- [x] Live: `check-setup.sh` exits 0 every row `ok`; `stack.py configuration` resolves
      `fork_repository` off the real notes branch; `refresh_dashboard.sh` renders this plan's
      own 50-item dashboard with zero drift; `plan_manifest_tools` answers both subcommands;
      `save-plan.sh` round-tripped this item's roadmap section.
- [x] Zero-install from a **fresh clone of the pushed branch**: import resolves to the clone's
      own copy, all ten entry points answer `--help`, `example-walkthrough.md`'s command runs
      verbatim.
- [x] `scripts/format_docstrings.py` on all 49 touched Python files.
- [x] Manifest recorded, roadmap section appended, PR description rewritten, #158 and #111 told.

## Findings worth carrying

- **A docstring claimed a guard that did not exist.** `plan_item_bootstrap.py`'s `ItemStatus`
  said *"a test holds the two equal"* — no test on `main` imports both modules. Same shape as
  the #154 review reply that described a contract test nobody had written; the cheap check is
  to grep for the import the test would have to make.
- **The precedence copy had already drifted**, so the second unification was a repair: the
  shell falls back to the current branch's upstream remote and `stack.py`'s Python copy did not.
- **A helper run by path cannot see the package** — an interpreter given a script path puts that
  script's directory on `sys.path`, not the working directory. Same reason every entry point is
  `python3 -m`.
- **`pip install` is its own verification.** Reading the manifest would not have found that
  `templates/`, `stack.toml` and `requirements.txt` were being left out.

## Open / carried

- **Not subscribed to tracking issue #102** — refused by the permission classifier. Concurrent
  structural changes reach a session here only via `plan-updates-since.sh`.
- **CI job rename** `test_claude_dev_tooling` → `test_bastler` changes the reported check name;
  branch protection needs updating if the old name is required. Flagged to the user, not acted on.
- **CI on the pushed branch not yet seen** — the robotics matrix takes a long time and is
  routinely red for reasons a `.claude/`-only diff cannot reach. `test_bastler` is the job that
  covers this diff.
- Re-drafted after the push, per the standing rule.
