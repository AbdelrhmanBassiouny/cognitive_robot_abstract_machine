## Next, if asked
The open thread is a small, contained follow-up: import `.claude/stack`'s runner instead, taking the
`sys.path` dependency. Left as a question rather than decided unilaterally.

## Outstanding — the user's, not this session's
- **One thread deliberately left open**: the git command runner (this package's own rather than
  `.claude/stack`'s, to avoid depending on another skill directory's `sys.path` insertion). The user
  closed the error-base and Artifact threads himself.
- CI on `8afbbe30` has not been checked — the no-scheduled-checks rule means it is not watched.
- The `d61619ac` commit message says "630 ... from 630"; the correct before-count is 611.
