# plan-item-bootstrap — draft PR #143

Item `plan-item-bootstrap` (plan `workflow-unification`, track `personal-data`),
based on fork `main`, `depends_on: []`.

## Plan

Two operations in one module, each caller taking only what it needs:

- **record** — write/update the item's `plan.yaml` entry + `roadmap.md` section,
  set its status, run `save-plan.sh`. `/add-plan-item` and `/plan-item-kickoff`.
- **open** — create + push the branch, open the draft PR, write `branch`,
  `session`, `pull_request_number` back and flip to `in_progress`.
  `/plan-item-kickoff` only.

Files: `.claude/hooks/plan_item_bootstrap.py`, its test module under
`.claude/hooks/tests/`, one appended constant block in
`resolve-personal-notes-config.sh`, a new post-approval step 6 in
`plan-item-kickoff/SKILL.md` (whose opening promise is rewritten), one line in
`.claude/hooks/README.md`, and one line on #135's branch (permission granted).

## Done — implementation complete

- Bootstrapped by hand in the order the item prescribes: branch, draft PR #143,
  manifest, roadmap, dashboard, then code. Subscribed to #143 and to #102.
- `plan_item_bootstrap.py` + 21 tests (57 under `.claude/hooks/tests`, was 36;
  194 plan-dashboard, unaffected). Each test mutation-checked.
- Constant, `plan-item-kickoff` step 6 + rewritten opening promise, README line.
- Live probe (#144, closed): creation succeeds, `draft: true` honoured, but the
  script's PR is attributed to `claude[bot]` while the session's tool attributes
  it to the user. Design changed for it — `open` takes `--pull-request-number`
  for a PR the caller already made; the creating path stays for unattended runs.
- One line pushed to #135's branch (`4186b3f7`) with a comment explaining it.
- Plan manifest + roadmap updated with the probe findings; dashboard republished;
  #143's description rewritten to match what it now does.

## Review round 2026-08-04 — 19 comments, applied in `1b95bee8`

- The manifest's vocabulary now has one home: `PlanField`, `PlanDocument`,
  `HookScript`, `ItemStatus`, `ItemFieldLine`. Tests import them and assert on
  rendered lines; `FOLDED_FIELD_PATTERN` is generated from `FOLDED_PLAN_FIELDS`;
  test paths resolve through the production `PlanLocation`.
- Test manifest/roadmap moved to `tests/fixtures/` as real `.yaml`/`.md`.
- Refusals are dataclasses with typed context + `suggest_correction()`, per
  krrood's `DataclassException` idiom in a stdlib-only base (decision 12).
- Step 6 now names both places the approved plan is written: `roadmap.md` via
  `record`, and the PR-progress note via `save-pr-progress.sh`.
- 60 tests under `.claude/hooks/tests` (was 36 at branch start). 17 of 18
  threads replied to and resolved.

## Second review round 2026-08-05 — 5 comments, applied in `df4f0225`

- `PlanField` members carry a `FieldSpecification` dataclass value (key, quoted,
  spans-following-lines) via `__new__`, keeping the member equal to its key.
  `render` moved onto the field; `ItemFieldLine` and its `quoting` are gone.
- `PlanDocument.path_within_notes_branch` names the plans directory once;
  `PlanLocation` collapsed to `fetch_notes_branch`. A test holds
  `PLANS_DIRECTORY` equal to the shell's `PLANS_DIR`.
- Docstrings on every enum member and on the test module's constants; the
  fixture docstring no longer explains the design it replaced.
- 257 tests, was 254. Three mutations checked. All 5 threads replied + resolved.

## Third round 2026-08-05 — the mixin, applied in `b1bc98f5`

- `ManifestKey(KeySpecification, Enum)` replaces the `__new__`: a member *is* a
  specification, so `isinstance`/`issubclass` hold and `.style` is direct.
- Members are declared as argument tuples; a built `KeySpecification` is accepted
  silently and lands in `.key`, guarded by a test (breaking it fails 4).
- `name` is impossible — `Enum` reserves it. `key` is YAML's own term and dodges
  `dataclasses.Field`, which was already shadowed in the test module.
- Two booleans → one `ValueStyle` (`PLAIN`/`DOUBLE_QUOTED`/`BLOCK`); `BLOCK` is
  correct for both `notes` (folded scalar) and `blockers` (sequence).
- 259 tests, was 257. Three mutations checked.

## Same round's last comment — the mapping, applied in `7352cfb7`

- `apply_item_fields` takes `dict[ManifestKey, str]`, not a list of pairs: the
  list accepted the same key twice and let the second write silently win, which
  a dataclass of pairs would have kept and a mapping cannot express.
- Same shape for `render_new_item`'s body and the required-keys check.
- Insertion order still governs line order; pinned by a mutation check
  (reordering fails only the field-order test). 259 tests, unchanged — refactor.
- All 19 + 5 + 1 review threads on this PR replied to and resolved except the
  one below.

## The duplication question, applied in `fbe6b90b`

- Asked whether anything here duplicates `stack.py`. Measured: the two
  `ExitCode` enums share only `SUCCESS = 0` and reuse 3/4/5 for unrelated
  meanings, `stack.py` makes no network call and never touches `plan.yaml`,
  and the only literal overlap is git boilerplate with opposite contracts.
- So the docstring's promise to align the two later described a unification
  with no content — deleted. `ExitCode` also gained the per-member docstrings
  it was the one enum in the file still missing.
- The one real duplication is `stack.py`'s own: it reimplements the
  notes-branch precedence the shell owns. Recorded on
  `dev-tooling-config-shim-slimming` as a second carrier for its planned
  consistency test.

## State 2026-08-05 — merged main, promoted, out of draft

- Head is `f77794b0`, a merge of `origin/main`. The routine reported a conflict
  and it was real: `.claude/hooks/README.md`, where main gained #115's
  `plan-updates-since.sh` bullet in the same list this branch extends. Both
  kept. `resolve-personal-notes-config.sh` auto-merged; checked semantically —
  `PLAN_ITEM_BOOTSTRAP_SCRIPT` and main's `PLAN_STATE_SYNC_STAMP`/`STACK_*`
  blocks all present. 367 tests, CI's scope now three directories (the stack
  suite arrived with #106).
- Reported on #139, then **corrected**: the first report (14:10) named no files
  while merge-tree named exactly one, which read as "detection right, naming
  empty". A second pass (20:37) disproved that half — it reported a conflict on
  `origin/main` `0626bdce` vs `f77794b0` where `merge-tree` exits 0 and GitHub
  says `clean`, and re-applied `needs-resolution`. main had not moved since
  14:27 UTC, so both passes ran on pinned, re-testable inputs. A false positive
  withholds a healthy branch from every later pass, and it was labelled while
  already `clean`, so detection and the clearing check disagree within one pass.
  Cleared the label myself (full set re-sent, `in-review` survived).
  One hypothesis covers both symptoms: any failed integration classified as a
  conflict, with unmerged paths enumerated from a state that has none.
  Their own live-pass notes cover a third, separate defect (promote stripping
  `needs-resolution` from a board-time snapshot).
- The user marked it ready and promoted it: label is now `in-review`, so it has
  been sent to cram2. Not re-drafted — the standing rule fires when *I* push,
  and their flip is the explicit signal it asks for. Any further push re-drafts
  it again.
- CI: `test_claude_dev_tooling` green on `f77794b0`, no failures anywhere. The
  earlier reds were container-setup `apt` failures before any test ran (`xvfb`
  deps at the bootstrap commit, an `archive.ubuntu.com` mirror-sync mismatch on
  `7352cfb7`); `test_quizzes.sh` passed on the next commit, confirming transient.

## Merged 2026-08-09 — item done, session's job on #143 over

- #143 merged into fork `main`. Verified by content, not the notification:
  `f77794b0` is an ancestor of `origin/main`; `plan_item_bootstrap.py`, its
  tests and fixtures are present; `SKILL.md` carries step 6 and the config
  file carries `PLAN_ITEM_BOOTSTRAP_SCRIPT`.
- Manifest set to `done` with a landing note, roadmap section added, dashboard
  republished (38 items: 14 done / 11 in progress / 13 not started, no drift).
- **Fourth stale-save revert, caught and re-applied.** My save landed at
  `96d9a47f`, and 5 seconds later another session's `b28375ea` wrote back a
  manifest loaded before it — reverting this item to `in_progress` and deleting
  the roadmap section, while legitimately marking #124 done. Re-applied onto
  their version; both correct now. Verified after writing, which is the only
  reason it was caught.
- Teardown done: unsubscribed from #143 (automatic), no subscription held on
  #102, and no triggers armed by this session (newest in the account is
  2026-07-29, all `run_once_fired`). Nothing left armed or watching.

## Next

- **One open thread, waiting on the user**: whether to re-base this item onto
  the upstream chain to unify `ItemStatus` with `build_dashboard.py`. Replied
  that basing on #111 would *not* unify it (that file only moves in
  `dev-tooling-python-package`, `not_started`), and recommended leaving the
  five-member overlap to that migration. Do not act until they answer.
- CI: `test_claude_dev_tooling` — the only job this `.claude/`-only diff reaches
  — is green on `7352cfb7`. The reds are container-setup `apt` failures before
  any test runs (`xvfb` deps at the bootstrap commit, an `archive.ubuntu.com`
  mirror-sync mismatch on `7352cfb7`), both noted once on the PR. Nothing to fix
  from this branch.
- Residue needing out-of-harness deletion: the remote branch
  `claude/plan-item-bootstrap-probe-vocs6b` (sessions cannot delete branches).
