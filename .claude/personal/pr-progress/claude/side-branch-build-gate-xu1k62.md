
# PR #425 - side-branch build gate

Every integration candidate died on `Run the maintenance pass`, from
`stack-maintenance.yml` (#280), which a build carries and which GitHub therefore
runs on the candidate itself. It judges the whole fork (a branch withheld as
conflicted -> exit 10) and the verdict counted it.

## Plan
- Stop the pipeline's own workflows deciding a build, in a way that does not
  depend on the reading checkout carrying their files.
- Carry out the review's rename of the package.

## Done
- Round 1: added `INTEGRATION_CHECKS` and `STACK_MAINTENANCE` to
  `PIPELINE_WORKFLOWS`, with a presence guard so an absent file did not crash
  the rebuild. Left a known limit: it only bit from a checkout holding
  `stack-maintenance.yml`, and nothing published carries both.
- Round 2 (`926c5f8712`): closed that limit properly. The exclusion now goes by
  the workflow file GitHub says each run ran from, read off the runs started on
  the head under judgement, instead of by job names read out of a local file.
  Verified against candidate #421's head: 25 check runs, exactly 4 check suites,
  one per workflow run. New client call `runs_started_on`; the exclusion moved
  from `ReportedChecks.of` into `read_checks`.
- Round 2 (`ad6adfffdc`): renamed `bastler` -> `basstler` across the whole tree,
  169 paths and 130 files. Both review threads replied to and resolved.
- 1165 tests pass; formatter and `black --check` clean. PR back in draft.

## Decisions
- Went by workflow identity rather than by reading the workflow out of the judged
  tree via git: no fetch dependency, no YAML, and it cannot mistake a repository
  job for a pipeline one just because they share a name.
- Redid the rename over the whole tree rather than merging #185's head, whose
  rename commit predates the file set this stack added.

## Next
- Nothing outstanding in this session. CI on #425 left unwatched by standing
  preference.
- The rename is still missing from #185's other descendants: `ixbvxl` and #211
  were cut from #185 before its rename commit, so they want restacking onto its
  current head. Only this branch is fixed.
- #425 remains a fold candidate for #211 - it only edits #211's files. Folding
  means pushing to #211's branch, which this session is not allowed to do and
  which would re-draft a PR you have marked ready. Say the word and I will.
- Merging #280 into this stack conflicts on six files (the `.claude/stack/` ->
  `basstler/` relocation). That belongs to an integration triage pass.

