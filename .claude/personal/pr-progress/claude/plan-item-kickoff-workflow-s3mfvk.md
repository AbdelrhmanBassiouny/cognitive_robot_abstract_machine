## Next
- Nothing blocking. The PR is a draft; no default-branch change is needed or wanted.


## Watch
- Textual overlap with #188 (`resolve-personal-notes-config.sh`, `session-start.sh`'s test module)
  and #185 (the first). Both open, both on `main`; whichever lands second merges.
- No PR-activity subscription and no scheduled check-ins, per personal notes. The tracking-issue
  subscription was refused by the permission classifier, so this session is not on that channel.

## Plan
Item `session-branch-base` of plan `workflow-unification` (track `stack-tooling`), PR #199,
draft, based on `main`, labelled `bug`. Reasoning in `roadmap.md` under the kickoff entry and
the 2026-08-28 reversal.

**The default branch stays `integration`.** It is the fast-PR process - it puts
reviewed-but-unlanded work into every fresh checkout - and the kickoff's recommendation to flip
it back was wrong. The requirement is that a pull request be based on `main` or a parent pull
request, never on `integration`; where a clone starts and where a branch is cut from are
separate events, and only the second can be a defect.
