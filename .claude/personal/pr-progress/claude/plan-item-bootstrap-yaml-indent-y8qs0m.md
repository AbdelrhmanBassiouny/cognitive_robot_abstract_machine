# PR #160 - plan_item_bootstrap wrote item fields at the wrong indentation

Bug fix off `main`, workflow-unification item `plan-item-bootstrap-yaml-indent`
(track personal-data). Draft, `bug` label.

## Plan

1. Failing tests first: an indentless fixture manifest, patched and read back. (done)
2. Read the depth off the manifest instead of hardcoding it. (done)
3. Surface `save-plan.sh`'s own message instead of swallowing it. (done)
4. Make the success report evidence: read the plan back after saving. (done)
5. Record the item and publish the dashboard. (done)

## Done

- `ItemIndentation` reads the marker off the item block being patched, or off the
  manifest's first item when appending; `ManifestKey.render` takes it, so no call
  site can assume one.
- `PlanSaveFailedError` (exit 9) carries what `save-plan.sh` said; `PlanNotWrittenError`
  (exit 10) fires when the notes branch does not carry the edit after a save.
- 7 new tests + a `bootstrap-plan-indentless-items.yaml` fixture and an
  `indentless_plan_repository`; hooks suite 36/36 in-module, 97 overall, plus
  plan-dashboard (218) and stack (154) green. All CI-safe: no network, no credentials.
- Verified against the real `rdr-refactor` manifest (`d-core-single-class` patches and
  parses), and this item's own manifest entry was written by the fixed script.

## Next

- Nothing outstanding on my side. `test_claude_dev_tooling` (the job that runs
  `.claude/hooks/tests`) is green on #160; the unrelated per-library jobs were still
  running when this was written and are not being watched. The PR is the user's to review.
- Left alone deliberately: `rdr-refactor`'s §20 account still says the defect is unfixed -
  correcting it belongs to that plan's roadmap, not this branch.
