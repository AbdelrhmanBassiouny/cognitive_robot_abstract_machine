# bastler-package — PR #185 (draft), branch `claude/plan-item-kickoff-workflow-cuare2`

Plan `workflow-unification`, track `bastler`, wave `upstream`. Kicked off and implemented in
session https://claude.ai/code/session_01JN9p5Kf2DKtzryspPX2KqZ; merged `main` and worked the
2026-08-22/23 review round in https://claude.ai/code/session_01Hgt7hWYnT9ZMK6AgusPwkk.

Create the `bastler` package and move every Python module under `.claude/` into it, so the
three separate `sys.path` roots stop preventing any shared definition from existing. Full
rationale in the plan's `roadmap.md` under the 2026-08-20 kickoff, the 2026-08-21
implementation, and the 2026-08-23 resolution.

## Done

- [x] Skeleton, `pyproject.toml`, contract tests (`39bc17c27`); the move (`a4405fbd5`);
      package data for an installed copy (`a826533b4`).
- [x] **Merged `main`** (`13bda614`). Not three conflicts but three modules: `main` gained
      `check_scope_overlap.py` (#135), `record_dashboard_url.py` (#150) and
      `upstream_reviews.py` (#146) under `.claude/` after this branch was cut, so resolving
      only the reported conflicts would have merged and then failed this branch's own
      "no `.py` under `.claude/`" contract.
- [x] **Metadata and self-declaration** (`52b44390`): empty `__init__.py` + `bastler/README.md`,
      full `pyproject` metadata, repository versioning via `scripts/sync_version.py`,
      `bastler/package_layout.py`, `ItemStatus.display_label`.
- [x] **Constants and the runner hierarchy** (`db910e90`): derive module names/paths from the
      import; `test/bastler_test/constants.py` for what has no import;
      `script_runner.py`'s `ScriptRunner`/`PythonModuleRunner`/`BashScriptRunner`.
- [x] **Fixture consolidation** (`4e8ad6fb9`): `PersonalNotesPath`, `install_hook_scripts_into`,
      `ScratchRepository.install_stack_configuration`.
- [x] 616 tests pass (479 on `main` before the move). `check-setup.sh` exits 0, every row `ok`;
      all thirteen entry points answer `--help`.
- [x] Manifest, roadmap section, PR description all current.
- [x] **Dead members of the declaration deleted** (`d13afaf8b`): `REQUIREMENTS_FILE`,
      `MODULES_BY_NAME` and `PackageModule.path` had no reader anywhere. 616 tests still pass.

## Findings worth carrying

- **A grep over the hooks is not a survey of the callers.** The tier's justification was
  measured against `session-start.sh`, which reaches no module here - and the conclusion
  "nothing depends on the tier" was wrong. The live caller is
  `.github/workflows/upstream-reviews.yml`, which runs `python3 -m bastler.upstream_reviews`
  on a bare runner with **no `pip install` step**, so that module and `bastler.stack` must
  stay standard-library-only. Grep for the module, not for the callers you expect.
- **A conflict report names files; the dangerous ones are the files it does not name.** Three
  of the six were flagged by git's "added in `origin/main` inside a directory that was renamed
  in HEAD"; the other three had no tell at all. The check is one command:
  `git ls-tree origin/main` for the pattern the branch claims to have emptied.
- **The dependency tier's stated reason was false.** It claimed a hook may import only the
  standard library because a hook runs where nothing is installed. `session-start.sh` reaches
  no module of this package at all — bash plus one stdlib-only heredoc in `check-setup.sh`. The
  tier answers something narrower and real: whether an entry point runs before
  `pip install -r bastler/requirements.txt`.
- **A docstring claimed a guard that did not exist** (`ItemStatus`'s "a test holds the two
  equal"). Cheap check: grep for the import the test would have to make.
- **`monkeypatch.setattr` takes the attribute name as a string by signature**, so it cannot be
  derived from importing the value — but it is already guarded, because `setattr` raises when
  the attribute is absent.

## Open / carried

- **34 review threads answered in code; inline replies still to post.** Two were answered
  differently from what they asked and must not be resolved: the `monkeypatch.setattr` derivation
  (impossible, with the measurement) and the SessionStart auto-install (available, deliberately
  not taken).
- **Not subscribed to tracking issue #102** — refused by the permission classifier in the kickoff
  session. Concurrent structural changes reach a session here only via `plan-updates-since.sh`.
- **CI job rename** `test_claude_dev_tooling` → `test_bastler` changes the reported check name;
  branch protection needs updating if the old name is required. Flagged, not acted on.
- **`run_git` is now reachable** (`check_scope_overlap.py` landed on `main`), but the seam stays
  `bastler-notes-core-python`'s by name. #151's `Subcommand` is still unlanded.
- Re-drafted after each push, per the standing rule.
