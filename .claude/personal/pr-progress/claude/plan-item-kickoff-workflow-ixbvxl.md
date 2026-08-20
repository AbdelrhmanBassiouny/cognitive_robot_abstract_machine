# integration-branch (#154) — regenerated personal integration branch

`workflow-unification` plan, `stack-tooling` track. Branch
`claude/plan-item-kickoff-workflow-ixbvxl`, containing `main` (which carries #139)
and #151. Draft PR #154, head `434ace04` pushed 2026-08-20.
Sessions: https://claude.ai/code/session_01Ue4PvfV5LDxHGRRS5BZB4g (built it),
https://claude.ai/code/session_01AYLtTRh7uZu64oLpMhGjQR (parts A/B/C/E),
https://claude.ai/code/session_01RhwNdD7ChskkomV1TCiRLU (the 08-13 round; Part D split out),
https://claude.ai/code/session_01RXr6gpbCyaa9K3V8F5kwRk (the 08-19 round and the base merge),
https://claude.ai/code/session_01Ra51SAHQKy7TVYRG2HRERW (this one — the 08-20 test-hygiene round).

## Status: round answered and pushed, nothing uncommitted

620 tests across the three directories CI runs — **deliberately unchanged**, since this
round is test hygiene and a higher number would have meant something else came with it.
`test_claude_dev_tooling` green on `434ace04`. `mergeable_state: clean`, 0 behind `main`.

**Read the pull request before this note.** The previous entry here said "nothing is
outstanding, waiting on review" and was true when written; a twenty-thread round landed
six hours later. That is the second time this plan has recorded a statement outliving its
own condition — see the roadmap's 08-20 second entry.

**Part D is still not this branch's work.** `integration-branch-ci-verdict` owns it.
`integration_test_command`, `--test`, `--no-test`, `TestCommandNotConfiguredError` and
`_run_tests` all still exist here and all work.

## The 08-20 round, twenty threads — 14 resolved, 6 open

Almost all one ask: a branch name spelled in the arrange and again in the assert.

| thread | outcome |
|---|---|
| name each branch once (×8, `test_integration_selection.py` and `_build.py`) | done — swept the whole module, not only the tests commented on |
| `"first-tip-file"` etc. hardcoded (×3) | done — `ForkCheckout.file_added_by`, which `branch_from` itself now calls |
| `__all__` linter idiom → `# noqa: F401` (×2) | done — six modules; one carried the block **twice** |
| `INTEGRATION_SCRIPT` from `__file__` | done for the import half | **left open** (shared script registry declined) |
| remove the `create_*` factories | `create_pull_request_object` removed | **left open** (other six measured and kept) |
| why a set in `branch_names_in` | **left open** — kept, docstring now says why (set difference at `_failure.py:203`) |
| multiply by `len(report.tips)` | **left open** — multiplied by the arranged count; the literal form is vacuous |
| structured conflict detection | **left open** — structured half is the line above; marker named as `CONFLICT_MARKER` |
| delete the report-keys contract test | **left open** — the only guard left on the wire format |

## Next steps

1. Nothing outstanding on this branch as of `434ace04`. Waiting on review.
2. Six threads are open on purpose and each names what would close it. Three are
   straightforward if the user overrules: remove the six remaining factories, delete the
   report-keys test, build the shared script-path registry.
3. The reparent onto #151's branch stays wrong until #151 merges `main` — #154 already
   contains #151's head and is 195 commits ahead of it.
4. `needs-resolution` is left for the next maintenance pass to clear itself.
5. Not done, not asked for: `stage_conflict` builds its return document from bare
   `"conflicting_paths"` / `"worktree"` keys while `ReportKey.CONFLICTING_PATHS` exists —
   the gap the last round closed for `block-branch`. Flagged on the `_replay.py:137` thread.

## Worth carrying

- **A repeated literal is a defect when the two copies can drift, and not one when the
  second copy is the assertion.** Two of the round's asks would have replaced a literal
  with an expression that no longer said anything.
- **Mutation-check an ask before taking it literally.** `* len(report.tips)` passes a
  build that carried one tip of two; only an unrelated assertion caught the mutation.
- **A duplicated `__all__` is invisible to everything but a reader.** The second silently
  rebinds the first; no error, no warning, no test that could fail. It survived a
  1564-line file being split into seven modules.
- **A local test failure can be about which interpreter has `pytest`.** Not the container,
  as the previous entry concluded: `pytest` was a `uv` tool with its own interpreter while
  the dependencies were in `/usr/local/bin/python3`. One install, and all 620 pass.
