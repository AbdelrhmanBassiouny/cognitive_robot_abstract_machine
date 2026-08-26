## `unfetched-parent-branches` - implemented, pushed, no pull request opened

Tracked as `workflow-unification` / `unfetched-parent-branches` (track `stack-tooling`),
with the sibling item `session-branch-base` recorded `not_started`. Tracking issue #102
carries the structural record; the dashboard is republished.

**Done.** Commit `a70132eb6` on `claude/maintenance-tooling-pinning-gdod18`, based on `main`.
554 tests pass across the four directories CI runs, from 533.

- Layer 1: `referenced_branches` names both ends of every board entry; `load_stack` fetches
  that instead of the heads.
- Layer 2: `UnresolvableBranchError` for a ref that does not resolve, `GitCommandFailedError`
  for a failed `git fetch` - neither answers for a branch it could not obtain.
- Layer 3: `Stack.effective_parent` places a parent that has left the board from where its
  commits are (upstream base / another open branch / nowhere). `ReportAParentThatIsGone`
  hands the last case back to the branch's owner, labelled and commented like a conflict.

Every layer mutation-checked: reverting each one turns its own test red.

**Verified read-only against the live fork**, from the ref state that produced the silence:
`reparents` prints #64 -> `main`, #178 -> `montessori_fast_inline_monitor`, #192 -> `main`
where it printed nothing, and `next` lists #64 again.

**Two things the developer should know.**
1. The branch this session was handed was a local copy of `origin/integration` (HEAD
   `899a04aac`, never on the remote). Reset onto `main` and pushed fresh - nothing
   force-pushed, nothing lost. Its name is a harness artefact and does not name the work.
2. `test_a_non_zero_status_says_what_it_means_on_the_way_out` and
   `test_a_run_needing_a_credential_it_has_not_got_is_its_own_exit_status` hang in this
   container (subprocess -> configuration -> network fetch). Proven pre-existing by
   stashing the changes and watching them hang on unmodified code. Untouched; CI runs them.

**Pull request open.** Draft #198, `bug` label, based on `main`, session link in the body.
Nothing is outstanding on this item.

**Notes changed the same turn** (`.claude/personal/cram-notes.md`, Pull requests section):
finishing a piece of work now means opening its draft PR in the same turn without being
asked, and a pull request is never opened on the upstream repository unless the developer
accepts it in that session.

**Open, unstarted.** `session-branch-base`: set the fork's default branch back to `main` and
make a session refuse to work from a branch not derived from it. No branch yet.
