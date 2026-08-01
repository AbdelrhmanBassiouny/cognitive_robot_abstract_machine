## git-identity-from-personal-notes (plan: workflow-unification, track: personal-data)

Implemented and pushed as commit `ddf3d382`. **No PR opened yet** — awaiting the
user's go-ahead. Full plan: `/root/.claude/plans/idempotent-juggling-plum.md`.

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

**Next:** open the draft PR when told to (`bug` label: recommended *no* —
nothing is defective). Other unconfirmed recommendation now built in:
`needs-setup` as the no-identity-recorded status.
