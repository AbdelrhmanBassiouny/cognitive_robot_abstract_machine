## Review round on #211: the git layer, the API address book, and the split

**Status**: done and pushed. `d444a773` on #211 (the round), `3dafcf86` on #154 (the
`integration.py` split it asked for), `2d50158c` merging the split back into #211.
Both descriptions updated; manifest, roadmap and dashboard all current.
#211 is still a draft; #154 stays out of draft by the recorded decision - a draft is
excluded from every integration build.

### The seven threads
Five resolved, two left open on purpose.

- **no explanation / no abbreviations / no union** - `BranchRefspec` became
  `BranchPublication`, `publishing` (a factory forwarding its arguments) deleted,
  `under_its_own_name` added for the ten callers that publish a branch as itself.
- **`gitcommandrunner?`** - the fixture used `remote_reference`, which already existed,
  and `BRANCH_REFERENCE_PREFIX`. Left open: I asked whether `ls-tree` should go on the
  shared runner for one test caller.
- **hard-coded path** - `ApiResource` and `HttpMethod`, plus `_page`.
- **the `GitCommand` discussion** - answered with measurements, no change, left open.
- **the 400-line rule** ("ok do it on 154") - done, resolved.

### What the round found that nobody asked for
Removing the union failed 27 tests: `push_refspec` on the base and `push` on the
subclass were one git command under two names with incompatible signatures. One `push`
now, taking `ProposedPush`, which moved to `.claude/shared/` carrying a
`BranchPublication`, with the lease on it as `as_arguments`. `configure` and
`set_configuration` had byte-identical bodies.

`page_size` is a field and two GitHub reads spelled `per_page=100` past it. There was
no test module for `GitHubRepository` at all, so `test_maintenance_github.py` pins all
eleven addresses at a page size deliberately not the default - which is what makes that
mutation fail; the first version used 100 on both sides and passed it.

851 tests across the four CI directories, from 839. #154: 759, from 758.

### Outstanding
- The two open threads are the user's to close: the `GitCommand` seam (recommended to
  `bastler-notes-core-python`, which owns `git_interface.py` and has four callers
  waiting) and the `ls-tree` question.
- `integration_reproduction.py` is 419 lines - #154's, predates this, and the only file
  in `.claude/stack/` still over 400. Offered on the thread, not done.
- Unchanged from the previous round: the candidate-close fix reaches the schedule only
  when a build publishes, since the schedule runs the copy on `integration`. A
  `workflow_dispatch` on this branch or a hand push to `integration` is what does it,
  and a dispatch is a real rebuild that publishes on green - so neither was done.
