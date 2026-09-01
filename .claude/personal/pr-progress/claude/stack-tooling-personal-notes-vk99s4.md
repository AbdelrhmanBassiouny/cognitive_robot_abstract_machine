No PR of its own: this session ran `/plan-item-resolve stack-tooling-install
setup-personal-notes-script` (plus the user's follow-up to merge into and fix
conflicts with #110), and all work landed directly on the two existing item
branches rather than this session's own.

Done: found `test_claude_dev_tooling` red on both #107 and #110 with the
same collection error - `test_setup_steps.py` still imported
`SCRUBBED_ENVIRONMENT_PREFIXES` after the 2026-08-30 review round renamed it
to `SCRUBBED_VARIABLE_PREFIXES`, and `setup_steps.py` had no `HookScript`
member for `install_hook_scripts` to resolve it by. Fixed both on #107
(`bc53ec33`), verified 607/607 tests pass there, merged into #110
(`c08cde6e`, one conflict in `tooling_files.py` resolved by keeping both
branches' additions), verified 668/668 tests pass there. Both PRs' bodies
and the plan's `setup-personal-notes-script`/`setup-stacked-prs-skill` notes
updated; both PRs converted back to draft after the push, per convention.
Dashboard republished (no drift; both items now show "ready to review").

Next: nothing outstanding from this run. #107 and #110 are green and
mergeable; they wait on the user's own review (both were draft->ready
before this session touched them, so they may already have been reviewed
once - worth asking the user directly whether this session's fix needs a
fresh look before merging).

Follow-up same session: user asked why GitHub's native "Rebase stack" button
fails on #107 with a reported merge conflict. Diagnosed by reproducing it
locally (dry-run rebase, aborted, nothing pushed): #107's branch history
contains ~13 "merge main in" commits accumulated over its life, including
one (`f8bdcd07d`) that resolved a real add/add collision on
`.claude/hooks/tests/stubs/{gh,curl}.sh` (main independently created the
same filenames via a different landed PR). GitHub's stack rebase does a
*linear* rebase - it discards merge commits and replays only the original
non-merge commits in isolation - so replaying an early commit
(`fe18da426`) that predates that merge recreates the same add/add
collision, with no merge commit left to carry the resolution. Confirmed:
the dry-run conflicted on exactly those three files. Not caused by main's
9 newer commits (unrelated robotics/coraplex files, no overlap).

Asked the user to choose between an ordinary merge (safe, matches #107's
existing pattern) or squashing/flattening #107's history to make it
rebase-compatible (destructive, force-push, needs #110 force-updated too).
User picked the merge. Merged `origin/main` into #107 (`9931f7be9`,
clean, no conflicts - confirmed no file overlap beforehand), verified
607/607 tests pass, pushed; PR shows `mergeable_state: clean`, stayed
draft. Propagated into #110 the same way (`f53a27edc`, also a clean merge,
668/668 tests pass), pushed; also `mergeable_state: clean`, stayed draft.
GitHub's native rebase-stack button will still fail the same way if
tried again - the structural cause (merge commits in #107's history) is
unchanged - but both branches themselves are healthy, mergeable, and
CI-green. No manifest/dashboard update: no tracked field (status, PR
number, branch) changed, only routine sync-with-main housekeeping.
