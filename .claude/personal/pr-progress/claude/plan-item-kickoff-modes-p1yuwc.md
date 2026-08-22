## `plan-item-execution-modes` — #149 / cram2 #537

Two review rounds handled on 2026-08-22. Branch
`claude/plan-item-kickoff-modes-p1yuwc`; pushing it updates both pull requests.

### Done
- **Round 1 (cram2 #537, LucaKro, changes requested 2026-08-19)** — `735988448`.
  Read via `WebFetch`, since this session cannot reach cram2's API.
  `ModeSetting`/`SettingsFile` replaced the two label arguments; `ExitCode.USAGE`;
  `ReportKey`/`ReportStatus` behind a `Report` base; the stale `ask`-is-the-default
  docstring. Reply text handed to the user - this session must not write to cram2.
- **Round 2 (fork #149, six threads, 2026-08-22)** — `7cf38aab9`. Reversed two of
  round 1's calls: the wire-value contract test is deleted, and `as_document`
  becomes `as_json`. Plus `CommandLineOption` (so `--skill` is named), `Any` for
  every `object` hint, `SETTING_KEYS` deleted as derivable and unread, all path
  constants and `SettingsFile.origin` as `Path`, and `from None` explained in
  `ModeError`'s docstring.
- **Base merge** (`2132efa76`): `main` gained #135's `scope-decision.md` reference
  and **#146's `/upstream-reviews`** step, both in the sections this branch had
  moved into `plan-item-gathering.md`. Carried across by hand, not merged wholesale.
- All six replies posted on #149; four threads resolved, two left open.
- 522 tests across the three directories CI runs; `check-setup.sh` exits 0; the
  `resolve` document is byte-identical.
- Plan recorded: roadmap round, both item `notes`, `save-plan.sh` (`718147c45`),
  dashboard republished (52 items, 0 drift), issue #102 comment 5379695801.

### Next
- Nothing outstanding on this branch.

### Outstanding / flagged
- **Two threads open on purpose**: `from None` (answered, code unchanged in
  behaviour) and the `SETTING_KEYS` removal (a deletion, not the rename asked for).
- The six threads on cram2 #537 are still unanswered there. `/upstream-reviews` is
  on `main` now, so a future resolve can read them without `WebFetch`.
- `report-document-naming` carries a decision it cannot dodge: `as_json` already
  names the `str`-returning method in `maintenance_report.py`/`maintenance_board.py`,
  so applying the rule repo-wide makes one name cover a dict and its serialized
  text. Recommendation recorded: dict keeps `as_json`, the `str` ones become
  `as_json_text`.
- `plan.yaml` still has no field for a promoted upstream PR.
- CI on `7cf38aab9`: `test_claude_dev_tooling` green, 16 docker-matrix jobs still
  running at hand-off. `mergeable_state` back to `unstable` from `dirty`.
- #149 left un-drafted: un-drafting a fork PR is this workflow's promotion gate.
