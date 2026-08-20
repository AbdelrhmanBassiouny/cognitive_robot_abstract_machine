
# integration-branch (#154) — regenerated personal integration branch

`workflow-unification` plan, `stack-tooling` track. Branch
`claude/plan-item-kickoff-workflow-ixbvxl`, containing `main` (which carries #139)
and #151. Draft PR #154, head `35eed0dd` pushed 2026-08-20.
Sessions: https://claude.ai/code/session_01Ue4PvfV5LDxHGRRS5BZB4g (built it),
https://claude.ai/code/session_01AYLtTRh7uZu64oLpMhGjQR (parts A/B/C/E),
https://claude.ai/code/session_01RhwNdD7ChskkomV1TCiRLU (the 08-13 round; Part D split out),
https://claude.ai/code/session_01RXr6gpbCyaa9K3V8F5kwRk (the 08-19 round and the base merge),
https://claude.ai/code/session_01Ra51SAHQKy7TVYRG2HRERW (this one — all three 08-20 rounds).

## Status: six rounds answered and pushed, nothing uncommitted

620 tests across the three directories CI runs — where the day started. One test added
for the `stage-conflict` document, which nothing was looking at, and two deleted on
review for the wire format, which nothing is looking at now.

**The report wire format is deliberately unguarded**, and the pull request description
says so. Measured after the deletion: renaming `ReportKey.EXIT_CODE`'s value to
`exitCode` leaves all 226 tests in `.claude/stack/tests` passing. Closing it belongs to
`integration-branch-ci-verdict`, which introduces a consumer that actually runs. `mergeable_state: clean`, 0 behind
`main`, still a draft.

**Read the pull request before this note.** Two consecutive entries here have said
"nothing is outstanding, waiting on review" and been overtaken within hours — once by a
twenty-thread round, once by a five-comment one. This note is a claim about a moment.

**Part D is still not this branch's work.** `integration-branch-ci-verdict` owns it.
`integration_test_command`, `--test`, `--no-test`, `TestCommandNotConfiguredError` and
`_run_tests` all still exist here and all work.

## The 08-20 rounds — 75 threads total, 65 resolved, 10 open

First round (20 threads, `434ace04`): a branch name spelled in the arrange and again in
the assert; the `__all__` linter idiom across six modules, one of which carried it twice;
`ForkCheckout.file_added_by`; `create_pull_request_object` removed.

Second round (5 threads, `f09e110f`):

| thread | outcome |
|---|---|
| bind the branch object, not its name — everywhere | done; also removed a duplicated `number` and a local shadowing its own result |
| `branch_names_in` should return the iterable | helper deleted — the set was its only content, and `git.branch_names()` is already a tuple |
| `stage_conflict`'s bare `"worktree"` / `"conflicting_paths"` | `StagedConflict` keyed through `ReportKey`, pair named `branch`/`attributed_to`, new document test |
| what does "pytest collects it as a fixture" mean? | explained and measured; comment reworded across six modules |
| delete the report-keys contract test | **left open** — documented with the worked example instead, as asked in the follow-up |

Fourth round (1 comment, `78c90007`), same thread: *"can you make a test that reproduces
the situation that this test fails in?"* The situation is a rename nothing catches, so
reproducing it is a mutation — but asking found that the test compared the enum against a
written-out copy of itself and never rendered a document. It reads the four real documents
now, which made the missing half free: a second test asserts the collected keys equal the
enum, catching a member nothing emits and a key emitted outside it. Measured: renaming
`EXIT_CODE`'s value gives 226 passed, 1 failed out of 227.

## Next steps

1. Nothing outstanding on this branch as of `35eed0dd`. Waiting on review.
2. Nine threads are open on purpose. Straightforward if the user overrules: remove the six
   remaining factories, delete the report-keys test, build the shared script-path registry.
3. The reparent onto #151's branch stays wrong until #151 merges `main` — #154 already
   contains #151's head and is 195 commits ahead of it.
4. `needs-resolution` is left for the next maintenance pass to clear itself.

## Worth carrying

- **A helper whose only content is a type conversion is a docstring explaining a
  surprise.** `branch_names_in` and `create_pull_request_object` both died the same way:
  pass the one value at the call site and nothing remains.
- **Bind the object, not its name.** `parent=bottom.name` is a reference; `parent=bottom`
  with a string local is a third copy that happens to agree.
- **A document built inside the method that returns it has its field names written once,
  in the only place nothing is looking.** Second instance in this module, after
  `block-branch`.
- **A repeated literal is a defect when the two copies can drift, and not one when the
  second copy is the assertion.** Two of the previous round's asks would have replaced a
  literal with an expression that no longer said anything.
- **A test that pins a contract must read the artifact the contract is about.** The
  report-keys test named the right hazard, was defended across four rounds, and checked
  the wrong object throughout — it asserted the enum against a copy of itself. The cheap
  check is what the test *imports*: a wire-format test that imports no serializer is
  asserting something other than the wire format.
- **Fixing that is what made the real question askable**, and the answer went the other
  way: it was deleted in the round after. Is one deliberate line per breaking change worth
  it when no reader executes the contract — that is the owner's call, not a measurement,
  and it could not be put properly while the test was checking the wrong thing.
- **A local test failure can be about which interpreter has `pytest`.** It was a `uv` tool
  with its own interpreter while the dependencies were in `/usr/local/bin/python3`. One
  install, and all 621 pass.

