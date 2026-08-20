## Branch `claude/pr-183-remove-ensure-ormatic-on141l`

Asked for: remove `ensure_ormatic_interfaces` from PR #183 - only the
regenerate script is wanted.

Plan: branch off #183's head (`claude/fix-ci-failing-tests-202965`), drop the
build-only-if-missing path everywhere, keep `regenerate`.

Done (commit 80bc4166, pushed):
- deleted `scripts/ensure_orm_interfaces.py`
- removed `WorkspaceOrmInterfaces.ensure_generated`/`are_generated` and
  `OrmInterface.is_generated` (the last two existed only to serve it)
- dropped the three tests of that behaviour; the regeneration tests still
  cover dependency order, clearing, and filling every interface
- docs/CI/ignore comment (`doc/contributing.rst`, `AGENTS.md`, `.gitignore`,
  `.github/workflows/ci.yml`) now name only `scripts/regenerate_all_orm.py`
- ran the ORM interface tests outside the root conftest (no deps in this
  container for the full suite): 15 passed

Landed on #183: pushed 80bc4166 to `claude/fix-ci-failing-tests-202965`
(fast-forward from df64ab60), and rewrote the PR body's closing paragraph,
which had offered `ensure_generated()` as an alternative to `regenerate()`.
The branch `claude/pr-183-remove-ensure-ormatic-on141l` holds the same commit.

Left #183 ready-for-review rather than re-drafting: it was already ready when
this session started, which by the notes means the user marked it ready.

Next: nothing outstanding. CI on the new head has not been checked.
