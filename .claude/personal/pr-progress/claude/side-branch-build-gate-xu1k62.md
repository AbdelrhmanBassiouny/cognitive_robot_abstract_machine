# PR #425 - side-branch build gate - FOLDED AND CLOSED

Folded into #211 on 2026-09-19 and closed unmerged. Nothing outstanding here.

## What it was

Every integration candidate died on `Run the maintenance pass`, from
`stack-maintenance.yml` (#280), which a build carries and which GitHub
therefore runs on the candidate itself. It judges the whole fork (a branch
withheld as conflicted -> exit 10) and the verdict counted it.

## How it ended

- Round 2 closed the real limit: the exclusion goes by the workflow GitHub
  says produced each run, read off the runs started on the head under
  judgement, rather than by job names read out of a local file. Verified
  against candidate #421's head: 25 check runs, exactly 4 check suites, one
  per workflow run.
- It only ever edited #211's files, so it was a fold candidate from the
  start - stacked only because this session was pinned to its own branch.
  Folded as `b9de8d0200` on #211, eleven files byte-identical to this
  branch's, with its own rename dropped as redundant.

## The one thing this branch had wrong

Its `bastler` -> `basstler` rename missed
`test/basstler_test/dataset/set-up-clone/bastler/{__init__.py,pyproject.toml}`,
and the check that cleared it grepped file *contents*, which cannot see a
stale directory name. The naive path filter misses them too, because
`basstler_test` earlier in the path matches the exclusion - splitting on `/`
and testing each component is what finds them. #211 carries them at the
right spelling.

## Next

Nothing on this branch. #211 and #154 are restacked onto #185 and carry the
rename; both left out of draft, as you had them.
