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
all three #126 runs — constant, so reproducible rather than flaky, and
pre-existing. One #126 run additionally hit `test_world_sim_state_sync` (the
known physics-settling flake; failed in one of three runs). The diff adds only
`.claude/hooks/` files, zero mention of `semantic_digital_twin`.

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
