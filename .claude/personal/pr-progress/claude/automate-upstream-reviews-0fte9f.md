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

## Review round 2 2026-08-07 (8 comments), applied in `7b2cee5f`

Mostly renames: "transport" named the layer rather than the thing, so
`GraphQLClient`/`GitHubCommandLineClient`/`.client`; every parser is `from_json`;
`PayloadKey` is `PullRequestJSONKey`; the report's subject is
`current_pull_request_reviews` and its fixed lines are a `ReportText` StrEnum.

The one that mattered: the tests still indexed the raw payload with enum keys —
the exact access path the mirror dataclasses exist to remove. Having built the
mirror in production and not used it in the tests was the inconsistency.
`FixtureName.recorded()` reads a fixture through `RepositoryPayload` now, and
`RepositoryPayload.pull_request_reviews` stops the raw node escaping at all.

Deliberately not converted, flagged for the user: one parser test still states
its expected values (a line number, a comment identifier, two booleans). A test
that reads its expectation back through the parser under test compares the
parser against itself and proves nothing. Everything else compares against the
recorded thread as a whole, which does check the reader's paging and ordering.

## Review round 3 2026-08-07 (4 comments), applied in `27b9bb3b`

`RepositoryPayload` is `RepositoryJSON` holding `data`; the word "payload" is
gone from the module; the two single-use expectations are inlined at their
assertions.

The one worth carrying: a blind `payload` → `data` substitution renamed
`GraphQLResponse.payload()` to `data()`, which the dataclass field of the same
name shadows — the client then called a dict and four tests failed with
`TypeError: 'dict' object is not callable`. It is `result()` now. A mechanical
rename across a file is exactly where a method and a field silently converge,
and without the transport tests this would have shipped as a runtime failure on
the first live run rather than anything a parse or import would catch. Also
swept the docstrings the substitution passed through ("the ``data`` data").

Whole `.claude/` suite is green at 371 — the two `test_check_setup_sh.py`
failures recorded above as pre-existing/environmental have since cleared.

## Spun out

Draft #147 off `main` carries the AGENTS.md rules the review asked for as a
separate PR. It *replaces* the existing one-liner "Instead of passing around
strings, use enums instead" rather than adding a duplicate, and adds the
testing half (assert against the definition; assert by type where a type
distinguishes the case). Documentation only, +8/−1. It has no plan item — a
repo-wide convention change rather than workflow-unification work — flagged to
the user rather than adding one unilaterally.

Review on #147 (2 comments), applied in `23b1a363`: the tuple bullet offers an
enum as well as a dataclass, and the JSON bullet became two, because reading
`krrood.adapters.json_serializer.SubclassJSONSerializer` showed the cases
differ — it resolves a concrete subclass from a `type` key *it wrote itself*,
so it serves our own classes round-tripping but has nothing to dispatch on for
an API response or a foreign configuration file, which still want a mirror plus
`from_json`. Flagged rather than caveated in the file: decision 12 fixes the
SessionStart-reachable tier as stdlib-only, so hook-safe code cannot import that
serializer even when the JSON is ours; "when possible" carries it until
`dev-tooling-krrood-adoption` revisits it. Subscribed to #147's activity, which
had been missed when it was opened.

## Review round 4 2026-08-08 (2 comments), applied in `1a478401`

`Connection`/`ParsedNode`/`nodes` are `JSONItemList`/`ParsedItem`/`items`, and
the type variable gained the docstring it was missing. The reviewer's question
was the whole correction: "connection" and "node" are GitHub's GraphQL
vocabulary, not this module's, so the class was named after the wrapper rather
than after what it holds, and only read to someone who had read those docs. The
docstring now states the shape plainly — GitHub returns `{"nodes": [...]}` where
a bare array would do — instead of encoding it in the name. 33 tests.

## The resolve-without-replying failure, and its correction

Recorded because it was a rule broken, not a rule missing. The user found
threads I had marked resolved with no inline reply, and one — the
mirror-dataclasses thread — resolved while genuinely half-done: the keys half
was there, the access path was still written out three times. Two things worth
carrying: I also claimed "31 threads resolved" when I had issued 20 resolve
calls, so the count was invented rather than counted; and the rule against this
was *already* in cram-notes.md. The notes are stronger now (reply first, resolve
second, one thread at a time; a PR-level summary is never a substitute; re-check
each part of a multi-part ask against the current file). Correction: the
half-done thread was unresolved and fixed in `4f1b2380`, and every thread I had
resolved silently now carries a reply saying what was done and in which commit.

## Naming rules → #147

The user's second ask on the `JSONItemList` thread: gather the naming problems
from this PR and recent ones into rules and put them in AGENTS.md as part of
#147. Done in `db843ee8`. Code Style already carried three naming bullets
scattered among unrelated ones, so they *moved* into a `### Naming` subsection
rather than being restated a fourth time — the same one-home treatment
`scope-decision.md` got, applied to the rule set that keeps being re-derived.
Each added rule traces to the review that produced it: `PreFlight` →
`CommitMoveChecks` (#139), `GraphQLTransport` → `GraphQLClient`,
`RepositoryPayload` → `RepositoryJSON`, `snapshot` → `read_current_state`,
`from_payload`/`from_data` → `from_json`, `SummaryMessage`'s stuttering members
(#121), YAML's `key` (#143), and the bound identifiers `Enum.name` /
`dataclasses.field` / a field shadowing a method (#143, #146). The last group is
the one with teeth — those fail at runtime rather than at import, and both
recorded instances actually happened. #147 re-drafted, description rewritten,
+22/−4.

The user then added the two rules that outrank all of those, in `2553ffd8`:
technically correct, simple, descriptive — in that order, because an inaccurate
name is worse than a vague one (a reader who trusts it stops reading) — and
minimize jargon, since a specialist or in-house term is a lookup the reader has
to perform and only earns its place where the plain word would be wrong. They
open the section rather than joining the list; everything below them is a
specific case of one or the other. +24/−4.

## Review round 5 2026-08-08 (3 comments), applied in `1012cce6`

All three landed on the `JSONItemList` introduced the round before, and following
the third one through deleted the class the other two were complaining about. The
reviewer asked to fold `parsed_into` into `from_json` so one call does the read;
once folded, `items` had nothing to carry between calls, so no class was left. The
read is a method on `PullRequestJSONKey` now — `PullRequestJSONKey.COMMENTS
.read_list(data, ThreadComment)` — which also answers the other two by
construction: the scope comes from where the method lives rather than from a name
trying to carry it, and the key names the entries at every call site. `nodes`
unwrapping went from two places to one; `ReviewThreadPage.from_json` takes the
`pullRequest` node so it reads through the same key. −70/+31, 33 tests, both halves
mutation-checked. Left unresolved: it answers the ask differently (delete the
wrapper rather than give it `from_json(data, model)`).

Worth carrying, and now a rule on #147 (`bfe28fbf`): **when no honest specific
name exists, suspect the code rather than your vocabulary.** "There isn't a more
specific name than `items`" was a true statement about a container that genuinely
had no single subject, and the fix was removing it rather than hunting for a
better word. Also worth noting the prototype-first rule paid again — the shape
only became visible by writing it.

`scripts/format_docstrings.py` cannot run in this environment (no `tqdm`, no
`docformatter`); `black` alone was run and left the file unchanged.

## Review on #147 round 2 (2 comments), applied in `f250275f` and #146's `3aaa7f0a`

Both were about the rules file and both improved it.

**Formalize a shared name.** "One operation, one name" was advice held by
discipline; the reviewer asked for a mixin or protocol that makes the method name
a requirement. The rule says so now, and it was applied to the code that produced
it in the same round rather than written and not taken: `read_list` was calling
`from_json` on an unbound `TypeVar`, so `JSONMirror(ABC)` declares it and
`ParsedItem` is bound to it. Chose the base class over a `Protocol` on a measured
ground — nothing type-checks `.claude/` in CI, so a `Protocol` documents without
enforcing, while the ABC makes a mirror missing the reader unbuildable. Note this
is the *opposite* of the `UpstreamReviewError` finding: `ABC` fails to enforce on
exceptions because `BaseException.__new__` bypasses the check, and enforces
normally on ordinary classes. Mutation-proved rather than assumed. 35 tests, was
33. Two models stay outside the contract with the reason in the base docstring;
formalizing the name is also what exposed that `GraphQLResponse.from_json` parses
text rather than an object, so it is arguably misnamed under the very rule —
flagged, not renamed.

**Remove the examples.** Every `X, not Y` pair read as a verdict on `Y`, when `Y`
was only wrong in the design it came from. Took the removal option; the rules
stand alone. Worth carrying: **an example in a rules file is a dependency on code
that will move.** One removed pair already named `JSONItemList`/`items` as good
practice, and that class had been deleted an hour later by the next review round —
so the file was wrong within a day of being written. Two kinds of backticked text
were kept and the judgment stated on the thread rather than made silently: the
umbrella-word list (the rule's content) and the bound identifiers (facts about the
language, not judgments about a design).

## Review round 6 on #146 (2 comments), applied in `820676cf`

`JSONMirror` is `JSONModel` — "mirror" was this module's own coinage where "model"
is the plain word, which is the minimize-jargon rule applied to the code that
prompted it. The word is swept from the docstrings and test names too.

The second comment is the one that taught something. The contract test listed its
four subjects, and the reviewer's objection was open/closed: a model added later
would not be covered until somebody remembered. Deriving the subjects removed the
list rather than fixing it — every class whose `from_json` takes only the object
to read — and the selection criterion *is* the contract's boundary, so the two
models that need more than the object exclude themselves rather than sitting on a
hand-maintained exception list. The test and the base docstring can no longer
disagree about who is covered.

Worth carrying: the derivation **widened** coverage from 4 to 7 immediately,
picking up `Author`, `ReviewThreadPage` and `RepositoryJSON` — models I had simply
not thought to list. A hand-written list of subjects is not just a future
maintenance cost; it is usually already incomplete when written.

Also recorded because it cost time: `cp file "$SCRATCH/orig.py"` with `$SCRATCH`
unset expands to `cp file /orig.py`, which *succeeds* as root, so the `||` fallback
never ran and a later restore brought back a pre-rename snapshot. Use an absolute
scratch path, and check `git diff --stat` after any restore.

## Review on #147 round 3 (3 comments), applied in `4cb02456`

All three were the minimize-jargon rule turned back on the file that states it,
which is the part worth carrying: **a rules document is the first place its own
rules should be applied, and it is the last place anyone thinks to check.**
"Umbrella word" became "generic word" and "stutter" became two plain clauses —
both were figures of speech a reader has to decode, three lines below a bullet
forbidding exactly that. The umbrella bullet's word list went too, which settles
the question left open in round 2: the user reads the no-examples instruction as
covering it. The section now carries no examples at all, and the only backticked
text left is the bound identifiers.

## #147 handed over 2026-08-08T21:12Z

The user marked #147 ready for review themselves, which ends this session's job on
it. Unsubscribed; nothing was armed for it (this session created no triggers, and
every trigger on the account is an already-fired `run_once_fired` from July
sessions referencing other pull requests). State at handover: head `4cb02456`,
+25/−4 in one file, mergeable, no labels, five review threads open — every one
answered, none needing action. One red check, `test_each_lib (robokudo)`, which is
the `gitlab.informatik.uni-bremen.de` outage rather than the diff; left alone
deliberately rather than re-run, since the job is done.

## Review round 7 on #146 (1 comment), applied in `bf8040d0`

`models_read_from_one_object` and its test removed on the user's instruction. The
lesson is about the round before it: I had answered "this list is not open-closed"
by deriving the list, when the better answer was that the guarantee was already
made by the abstract base and neither the list nor the derivation needed to exist.
Answering the objection as posed can still leave the wrong thing in place. 34
tests, was 35.

## Next

- #146 draft, waiting on the user. #147 is handed over — do not touch it.
- #146 carries one red `test_each_lib (robokudo)` from the same GitLab outage. A
  re-run was refused with `403 This workflow is already running` while sibling
  jobs were in flight; it still needs firing once the run completes. Threads on #146 that stay
  open by design: the `GraphQLClient`-as-ABC answer, the mirror-dataclasses one
  the user flagged, the naming one, and all three of round 5. On #147, both of
  round 2 stay open — one asks the user to check which examples count.
- Live dispatch is still blocked until #146 merges — `workflow_dispatch` only
  registers a workflow present on the default branch.
- `scripts/format_docstrings.py` cannot run in this environment (no `tqdm`, no
  `docformatter`), so only `black` has been applied to the recent commits.
