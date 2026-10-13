## Next
- Not doable from here: reading an upstream job log to name the actual error.
  api.github.com and github.com are both blocked for cram2 in a Claude session
  (403 "not enabled for this session"); `add_repo` read access is git-only. It
  needs a second reader that fetches the upstream job log from the fork's
  runner - new work, so a new branch, since #420 is finished.
- The integration build cannot publish while `claude/performatives-clean` (#14)
  stays conflicted against its base: that is what fails the candidate's "Run
  the maintenance pass" check (exit 10, BRANCH_NEEDS_ATTENTION).


## Next
- After #185 lands: the maintenance pass moves the base back to `main`, then rebuild the promotion
  link and promote.
- #424 needs #420's new head merged in. Seven conflicts are recorded on its plan item. It needs the
  user's go-ahead, because they marked it ready.


## Plan
Answer "what is the CI state of every in-review pull request, on the fork and
upstream, and is any red one already fixed elsewhere". The upstream half needed
a capability that did not exist, so this branch built it.
