## `/plan-item-resolve workflow-unification plan-item-execution-modes`

Resolve session for `plan-item-execution-modes` (fork PR #149, promoted upstream
as cram2 #537). The work landed on the item's own branch,
`claude/plan-item-kickoff-modes-p1yuwc`; this branch opened no PR of its own.

### Done
- Read #537's six review comments (LucaKro, changes requested 2026-08-19) via
  `WebFetch`: this session cannot reach cram2's API at all - `add_repo` refuses a
  cross-owner attach, `api.github.com` returns 403 - which is the gap item
  `upstream-review-reader` (#146) exists to close.
- Implemented and pushed `735988448` to `claude/plan-item-kickoff-modes-p1yuwc`,
  updating both #149 and #537:
  - `ModeSetting(key, value)` and `SettingsFile(path, origin)` replace
    `parse_mode`/`read_settings_file` and their label arguments; both refusals
    carry those objects instead of a second copy of the labels.
  - `ExitCode.USAGE = 2` as a member, mirroring `stack.ExitCode`, and the class
    now says why 1 is left free.
  - `ReportKey`/`ReportStatus` plus a `Report` base declaring the
    `as_document`/`exit_code` pair. The printed document is byte-identical.
  - Fixed the module docstring, which still named `ask` as the default.
  - One contract test pinning every wire value; mutation-checked (an exit-code
    change fails only that test).
- 498 tests pass across the three directories `test_claude_dev_tooling` runs;
  `check-setup.sh` exits 0; the CLI's JSON output is unchanged.
- #149's description updated with the review round. Left un-drafted on purpose:
  un-drafting a fork PR is this workflow's promotion gate, so re-drafting would
  withdraw #537 from the review it answers.
- Plan recorded: `roadmap.md` round section, `notes` on the item, new item
  `report-document-naming`, `save-plan.sh` (`d50d35a2f`), dashboard republished
  (51 items, 0 drift), issue #102 comment 5379695801.

### Next
- Nothing on this branch. The six reply texts for #537 were handed over in the
  session chat for the user to post; this session must not write to cram2.

### Outstanding / flagged
- The six threads on #537 are unanswered there.
- The krrood half of the serialization thread was declined, so that thread must
  stay open rather than be resolved.
- `plan.yaml` has no field for a promoted upstream PR, so an item under
  changes-requested review upstream looks identical to one quietly in progress.
- #149's CI on `735988448`: 18 green including `test_claude_dev_tooling`, 4 of
  the docker matrix jobs still running at hand-off, among them the
  `semantic_digital_twin` one that was red before on `test_world_sim_state_sync`
  - a physics settle assertion, not this branch's.
