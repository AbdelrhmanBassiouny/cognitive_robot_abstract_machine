## git-identity-from-personal-notes (plan: workflow-unification, track: personal-data)

Branch is at origin/main (82501888), no code written yet. Kickoff only — no PR yet.

**Plan** (full version: `/root/.claude/plans/idempotent-juggling-plum.md`):
sync the human git identity from the personal-notes branch into the clone at
session start, and add a `git_identity` row to `check-setup.sh`. Base off fork
`main`, no `depends_on`. Steps, test-first: (1) new
`tests/test_git_identity_sync.py`; (2) `resolve-personal-notes-config.sh` gains
`PERSONAL_GIT_IDENTITY_PATH`, `effective_git_identity`,
`repository_local_git_identity_is_set`, `recorded_git_identity`; (3)
`session-start.sh` identity block + summary line; (4) `test_check_setup_sh.py`
gains `SetupCheck.GIT_IDENTITY` and strips `GIT_AUTHOR_*`/`GIT_COMMITTER_*` in
its env scrub; (5) `check-setup.sh` row after `notes_file`; (6) new
`save-git-identity.sh` (`--name`/`--email` required, delegates to
`write-personal-notes-file.sh`); (7) README rows; (8) plan.yaml + roadmap.

**Key finding this session:** `GIT_AUTHOR_*`/`GIT_COMMITTER_*` are *set* in this
container to `Abdelrhman Bassiouny <abassiou@uni-bremen.de>` and commits here are
authored correctly — the roadmap's 2026-08-01 section records them as unset.
Correcting that is part of step 8. Consequence: the check must read
`git var GIT_AUTHOR_IDENT`, not `git config --get user.name` (which prints
`Claude` on a clone that commits correctly).

**Next:** await go-ahead to implement (kickoff writes no code). Two decisions
were recommended, not confirmed: `needs-setup` as the no-identity-recorded
status, and no `bug` label.
