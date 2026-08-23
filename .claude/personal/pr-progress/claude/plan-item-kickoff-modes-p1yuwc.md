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

### Addendum, later on 2026-08-22

- **A third review comment** (`# %% locations`, "put all these directories in a StrEnum?")
  was first answered with a measurement and no code change, on my call; the user then
  proposed a concrete shape and it was **implemented** in `1b2f79672`. `HOOKS_DIRECTORY`
  stays a plain `Path` constant *above* the enum, and the four file paths are
  `Location(StrEnum)` members composed from it, each with a `.path` property for the
  callers that do path arithmetic. `SettingsFile.origin` is a `Location`. Every call site
  loses a `str()` or gains one `.path`; the `resolve` document is byte-identical.
  Mutation-checked on `COMMITTED_DEFAULTS`; 18 module tests, 522 across the three
  directories. Thread replied to and **resolved**.
- **Two claims I made on that thread were wrong and were corrected on it** (reply
  `3836855129`): `.name` returns the member name under `StrEnum` but **not** under the
  `Path` mixin, where `Path.name` shadows `Enum.name` and answers the filename - so the
  sharpest objection I raised against the mixin was an objection to the other shape. And
  the mixin's cost is not only the 3.11 floor: on 3.12 it builds, then `f"{member}"`
  renders `Location.COMMITTED_DEFAULTS`, `.parent` and `json.dumps` raise, and by-value
  lookup raises.
- **The recommendation I recorded was superseded by the user's own shape**, which beats
  both options I had costed. Carried into `roadmap.md`: a measurement showing two asks
  conflict is not proof no third shape exists - before reporting two requirements
  incompatible, ask whether the collection can be split so each half gets the type it
  wants.
- **A claim corrected in two durable places.** The first round's justification for `StrEnum`
  said `ExecutionMode(value)` reads and `str(mode)` writes "with no lookup table between
  them", which is wrong about reading - by-value lookup is `Enum.__call__` and a plain `Enum`
  does it identically. Fixed in `roadmap.md` (in place, with the correction noted) and in
  #149's description. `StrEnum` buys the write/interop half only.
- Plan saved (`940099c8a`, then `b0577481c` for the `Location` round), dashboard
  republished twice (52 items, 0 drift both times). #149's description updated for the
  `Location` change.
- **Open threads on #149 are back to two**, not three: `from None` and the `SETTING_KEYS`
  removal. The six on cram2 #537 remain unanswered there.


### Round 3 (cram2 #537, tomsch420, changes requested 2026-08-23 09:58Z)

`/plan-item-resolve workflow-unification plan-item-execution-modes`, in `auto` mode
(committed default). Applied in `236247da`.

- **Nothing on the fork showed the stall.** 23/23 checks green - the `greenlet` and
  robokudo failures the 08-10 comments recorded have both cleared - `mergeable_state:
  clean`, `origin/main` an ancestor of the head, no conflict, the same two threads open
  on purpose. The block was entirely on cram2 #537, from a **second** upstream reviewer.
- **`/upstream-reviews` earned its keep on first use.** Read the round in ~12s via the
  dispatched Action, where the 08-22 round needed `WebFetch` on a rendered page. The
  prediction recorded that day held.
- **The ask**: *"we call it to_json everywhere else. Make yourself ready for
  SubclassJSONSerializer"*, on `Report.as_json`. Renamed the abstract method and both
  implementations to `to_json`; `Report`'s docstring now names the
  `SubclassJSONSerializer` contract it matches.
- **Third name in five days, first one measured.** `def to_json` is defined **93** times
  outside `.claude/`; `as_json`, `as_document` and `to_json_dict` together, **3**. The two
  earlier rounds were arguments; this one is a count that was available at every round.
- **Adopting the base class stays declined** on the CI measurement in the still-open
  krrood thread. "Make yourself ready for" is read as the name and signature, not the
  import. No `type` key added - that would change the printed document.
- **`report-document-naming`'s inherited collision is gone**, not resolved: with `to_json`
  for dict-returners, `as_json` stays free for the two `str`-returning ones and neither
  needs `as_json_text`. That item's target was corrected in the same turn.
- 522 tests pass (unchanged), the `resolve` document is byte-identical, `black --check`
  clean, `docformatter --diff` at 63 hunks - identical to before the edit, so no
  formatting drift.
- Plan saved (`ecfad954`), #149's description updated, dashboard republished.

### Next
- Nothing outstanding on this branch. Waiting on cram2 #537's reviewers.

### Outstanding / flagged
- **The reply to tomsch420 cannot be posted from here** (`AGENTS.md` forbids writing to
  cram2, and its API is unreachable) - handed to the user in the session chat.
- **Two fork threads still open on purpose**: `from None`, and the `SETTING_KEYS` removal.
- **The gap this round sharpens**: a fork PR can be green, un-drafted, conflict-free and
  current with its base and still be blocked upstream, with no field on the plan showing
  it. `plan.yaml` still has no field for a promoted upstream pull request.
- #149 left un-drafted again, deliberately: re-drafting would withdraw #537 from review.
