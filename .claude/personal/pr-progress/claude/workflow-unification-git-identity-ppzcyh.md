## git-identity-from-personal-notes (plan: workflow-unification, track: personal-data)

Draft **PR #126**, commit `ddf3d382`, subscribed to its activity. No `bug` label.
`test_claude_dev_tooling` green. Full plan:
`/root/.claude/plans/idempotent-juggling-plum.md`.

**Restacked 2026-08-02** by the stack routine: head is now `bb3f6a51`, merging
#121's updated branch (which had merged `main`) into `ddf3d382`. Local branch
fast-forwarded to it. Verified the merge is sound in substance, not just
textually: `56 passed` in `.claude/hooks/tests` on the merged tree (54 before,
plus #121's two new `session-start.sh` tests), all 12 git-identity tests green.

**CI red, not mine — diagnosed and answered on the PR, no fix pushed.**
`test_each_lib (semantic_digital_twin)` fails two `test_multi_sim.py`
material-builder tests (`assert '' != ''`) identically on the base #121 and on
all four #126 runs (two per commit, before and after the restack) — constant,
so reproducible rather than flaky, and pre-existing. `test_world_sim_state_sync`
additionally failed in exactly one of those four, which is the known
physics-settling flake behaving like one. The diff adds only `.claude/hooks/`
files, zero mention of `semantic_digital_twin`. Answered on the PR three times;
further identical runs are duplicates and get no further comment.

**Hypothesis ruled out after the restack:** the post-restack run has `main`
merged in (`1048 passed`, was 884) and the two failures survive it — so this is
*not* staleness relative to `main`, and merging `main` is not the fix. `main`'s
own push run at `82501888` still passes this job, so the divergence is between
push runs and `refs/pull/*/merge` runs. The restored asset cache
(`/github/home/.cache/semantic_digital_twin`) is the likelier place to dig than
the source tree. Not investigated further — different package, outside this PR;
worth its own item if it keeps reddening unrelated PRs.

**Base: #121** (`claude/workflow-unification-setup-jgvs53`), not fork `main` —
this reverses the item's recorded `depends_on: []`, now
`depends_on: [session-start-plan-and-setup-guards]`. Reason: `main` has *no*
harness that can run `session-start.sh` in a test; #121 adds
`ScratchRepository.run_hook_script` + `write_setup_prerequisites`. #109 was
rejected as a base outright (`dirty`, `needs-resolution`, stale base).

**Shipped:** `.claude/personal/git-identity` on the notes branch (git-config
format, read via `git config --file`); `session-start.sh` writes it to
repository-local config only when the clone has neither half, before the setup
check; `check-setup.sh` `git_identity` row; `save-git-identity.sh`
(`--name`/`--email` required, delegates to `write-personal-notes-file.sh`);
README + `personal-notes.env.example` rows. Env scrub moved onto
`run_hook_script`, replacing #121's two hand-rolled copies.

**Key finding:** `GIT_AUTHOR_*`/`GIT_COMMITTER_*` are *set* here to
`Abdelrhman Bassiouny <abassiou@uni-bremen.de>`; the #122 session had already
recorded this correction in the roadmap, mine confirms it independently. So the
check resolves via `git var GIT_AUTHOR_IDENT`, never `git config --get
user.name` (prints `Claude` on a clone that commits correctly).

**Verified:** 54 tests pass in `.claude/hooks/tests` (was 37), 248 across both
CI directories. Live in this clone: row read `needs-setup` naming the real
author, `save-git-identity.sh` recorded it, row went `ok`, re-run pushed
nothing. plan.yaml + roadmap saved, dashboard republished.

**Watch item:** #126 is based on #121, not `main`. If #121 lands by push or
fast-forward rather than through its own PR, GitHub will *not* retarget #126 —
round-2 of native-stacks-prototype established that only `merge-async` does.
Neither is a native stack member, so a plain `PATCH` of the base is the
recovery. If #121 merges normally, rebase #126 onto `main`.

**Next:** respond to review comments and CI events as they arrive (no timed
check-in). Unconfirmed recommendation now built in: `needs-setup` as the
no-identity-recorded status.

---

## Resolve pass 2026-08-11 (session_016kC5DfwqNRAmDkWYLxpa3x)

Item was `blocked`; now `in_progress`, blocker cleared. Head `edca885f`,
`mergeable_state` `dirty` → `unstable`, `needs-resolution` dropped, still a
draft, no `bug` label, description rewritten. Plan:
`/root/.claude/plans/imperative-honking-trinket.md`.

**Done**

1. Merged the base at `311354a3` (was `5baac7d8` — #121's own resolve, two
   review rounds, two `main` merges). Five conflicts, all additive-vs-additive,
   three carrying a real choice:
   - `session-start.sh`: our git-identity block vs `main`'s personal-settings
     sync at the same anchor. **This branch did not carry the settings block at
     all**, so keeping ours would have silently deleted it from the hook. Both
     kept, git identity first, both above the setup verdict.
   - `scratch_repository.py`: dropped `REQUIREMENTS_FILE`/`TOOLING_FILES` for
     #121's `SetupPrerequisiteFile` enum over the same paths; `run_git` keeps
     both its `cwd` argument and our `run_git_allowing_failure` delegation.
   - `README.md`: summary paragraph and gitignore bullet re-authored, keeping
     #121's third-person wording. Both merged files read end to end — no
     resurrected or stranded sections.
2. Folded the `git identity:` wording into `session-start-messages.sh` with
   `SummaryMessage` members; moved `SummaryMessage`/`summary_message` beside
   `summary_value` in `session_start_summary.py`, now shared by two test
   modules. Replaced `test_git_identity_sync.py`'s four literal copies of the
   wording. No wording pinned (per #121 round 2); mutation-checked that a
   missing function and a silent function each fail the contract test.
3. Replied to the `GIT_AUTHOR_IDENT` thread with the `git var -l` measurement
   and **left it open** — the rename cannot be applied, `GIT_AUTHOR_IDENTITY`
   does not exist.
4. 397 tests green (107 hooks / 194 plan-dashboard / 96 stack), re-run from a
   clean clone of the pushed branch. Live hook run in this clone reports
   `git identity: set from 'claude/personal-notes' ...` and `setup: ok`.
5. Manifest + roadmap saved (`31e253fe`), dashboard republished, structural
   comment on #102.

**Caught and repaired: a stale save.** The notes branch moved `7170e664` →
`49e0a3aa` while the edit was being composed, and the first `save-plan.sh`
reverted `manifest-currency-first`'s fold-bug repair across five items' notes.
Re-applied only this item's block onto `49e0a3aa` and re-saved; verified
semantically — 43 items, zero fields differing outside this item. The
fetch-before-write rule did not catch it because the window is between *reading*
and *writing*; diffing the push against the tip it landed on is what did.

**Outstanding**

- The `GIT_AUTHOR_IDENT` thread is open by design — the user's to close, or to
  redirect toward avoiding the bare token in prose.
- CI has not run against the merged tree yet. `test_each_lib
  (semantic_digital_twin)` is expected to stay red as the base's failure; check
  it on the new run rather than inheriting the 2026-08-03 ruling.
- The watch item above still stands: if #121 lands by push, #126 needs a manual
  base `PATCH` to `main`.
