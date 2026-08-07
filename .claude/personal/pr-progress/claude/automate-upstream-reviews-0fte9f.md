# upstream-review-reader — draft PR #146

Plan item `upstream-review-reader` (workflow-unification, `stack-tooling` track,
wave `upstream`, depends on `stack-tooling-on-main` which is done).

## The problem, and why the obvious solution is impossible

Reading cram2 review threads by hand and retyping them made the user the
bottleneck on every review round. Thread resolved-state — which the user made a
hard requirement — exists only in GitHub's GraphQL API, and GraphQL is refused by
the agent proxy for *every* repository including the fork's own ("only the pinned
set of PR-review operations is served"). So no script inside a session can produce
this report. The read runs on the fork's Actions runner instead; the session reads
the job log over plain REST.

Also established: cram2 is public and readable — `stack.toml` and `stack.py`
asserting it "is not readable from the cloud" is wrong. The session simply cannot
be the reader. Not corrected here (it touches `stacked-pr-maintenance`, whose tests
assert its wording); flagged for a follow-up.

## Done

- `.claude/upstream_reviews/upstream_reviews.py` — models, `gh api graphql`
  transport behind one seam, cursor pagination, unresolved-only by default.
- `.github/workflows/upstream-reviews.yml` — `workflow_dispatch` only,
  `permissions: contents: read`, no repository named anywhere.
- `.claude/skills/upstream-reviews/SKILL.md` — dispatch, poll, read log, present.
- `plan-item-resolve` step 2 gathers it, gated on `in_review_label`; failure is
  reported, not fatal.
- 29 tests, offline with `gh` stubbed. Stubbed end-to-end run verified branch
  resolution, pagination, resolved-filtering, step summary.
- Backend choice: `gh`, not a fourth hand-rolled client — answers what #139's
  review asked rather than deferring to `dev-tooling-github-api-unification` again.

## Next

- **Blocked until merge:** live dispatch returns 404 because `workflow_dispatch`
  only registers a workflow present on the *default* branch. Actions are enabled
  and 15 other workflows are registered, so this is that rule and nothing else.
  First real run — and the first exercise of the GraphQL document against the live
  schema — is only possible once this lands on fork `main`. That is the one
  residual risk.
- After merge: dispatch for cram2 #516 and #513. #513 is the discriminating check —
  its `"doc formatting"` thread on `maintenance.py:1031` is resolved and must be
  absent by default, while the "weird to have this randomly in the middle of the
  file" thread is unresolved and must appear.
- Two pre-existing failures in `test_check_setup_sh.py` reproduce on clean
  `origin/main` (the setup check probes system `python3`, which lacks pytest) —
  not from this branch, left alone.

## Review round 2026-08-07 (21 comments), applied in `bd159319`

One theme throughout: structured data over strings. Everything naming a fixed
thing is a `StrEnum` member now (`PayloadKey`, `QueryVariable`,
`GraphQLDocument`, `EnvironmentVariable`, `ReviewState`, `PullRequestState`,
`ThreadMarker`); the query documents moved into `.graphql` files, which
`AGENTS.md`'s no-inline-snippets rule had already required and the first
version simply did not follow; every model gained `from_payload`, and
`RepositoryPayload` owns the one access path so neither keys nor path are
written twice; errors are dataclasses with typed context; `snapshot` became
`read_current_state`; the tests no longer contain the reviewed file path,
comment bodies or URLs at all, comparing against the recorded payload and the
report's own `heading()`/constants instead. 32 tests, was 29.

Two things worth carrying:

- `GraphQLErrorsReturned` split out of `GitHubCommandFailed`. A failed process
  and a GraphQL error array are different failures, and separating them is what
  lets a test assert by type rather than on message text — which is the
  reviewer's stated preference over string matching.
- **`ABC` cannot enforce abstractness on an exception.** `UpstreamReviewError`
  gets the right metaclass and a populated `__abstractmethods__`, but
  `BaseException.__new__` bypasses the check `object.__new__` performs, so the
  base still instantiates. Kept for declared intent; the enforcement is not
  real and should not be claimed.

Deliberately answered differently from what was asked, and left unresolved for
the user: `GraphQLTransport` became an abstract base class rather than a
dataclass — it holds no data, it is the interface.

## Spun out

Draft #147 off `main` carries the AGENTS.md rules the review asked for as a
separate PR. It *replaces* the existing one-liner "Instead of passing around
strings, use enums instead" rather than adding a duplicate, and adds the
testing half (assert against the definition; assert by type where a type
distinguishes the case). Documentation only, +7/−1. It has no plan item — a
repo-wide convention change rather than workflow-unification work — flagged to
the user rather than adding one unilaterally.
