# integration-branch (#154) — regenerated personal integration branch

`workflow-unification` plan, `stack-tooling` track. Branch
`claude/plan-item-kickoff-workflow-ixbvxl`, containing `main` (which carries #139)
and #151. Draft PR #154, head pushed 2026-08-20.
Sessions: https://claude.ai/code/session_01Ue4PvfV5LDxHGRRS5BZB4g (built it),
https://claude.ai/code/session_01AYLtTRh7uZu64oLpMhGjQR (parts A/B/C/E),
https://claude.ai/code/session_01RhwNdD7ChskkomV1TCiRLU (the 08-13 round; Part D split out),
https://claude.ai/code/session_01RXr6gpbCyaa9K3V8F5kwRk (this one — the 08-19 round and
the base merge).

## Status: code done, round answered, nothing uncommitted

620 tests across the three directories CI runs, from 599. `test_claude_dev_tooling` —
the only job reaching this `.claude/`-only diff — green on the new head. All five entry
points run standalone. `mergeable_state` was `dirty` since 08-18 and is not.

**Part D is still not this branch's work.** `integration-branch-ci-verdict` owns it.
`integration_test_command`, `--test`, `--no-test`, `TestCommandNotConfiguredError` and
`_run_tests` all still exist here and all work.

## The 08-19 round, eighteen threads — 12 resolved, 6 open

| thread | outcome |
|---|---|
| rename `spelling` → `name` | done |
| rename `carried` → `integrated`, everywhere | done, plus the selection vocabulary and `README.md` |
| make `TipStatus` inherit the specification | **left open** — impossible, three measurements |
| remove the duplicated `carried` on the member | done — the member carries the specification instead |
| shorten `tips_of`'s docstring | done, 14 lines to 6 |
| `StrEnum` for `block-branch --json`'s keys | done, plus a `BlockedBranchReport` and its first test |
| why `cram2` in the tests | done — `UPSTREAM_REMOTE`, defined where the fixture registers it |
| use the git command runner | done — six new methods, no `run_git` left | **left open** (asked where they belong) |
| mirror schema for the report document | done — `from_json` per level |
| verify the `escalate` rename | done — it was incomplete; two more mangled names found |
| repeated literals in the block tests | done, swept |
| file over 400 lines | done — seven modules, largest 305 | **left open** (asked about `integration.py`) |
| nothing clears `integration-conflict` | **left open** — the marker half of the CI-verdict item |
| `blocking_labels` return type | **left open** — configured labels, not `DefaultLabel` members |
| `blocking_labels` onto `DefaultLabel` | **left open** — `configuration_key` moved there instead |
| remove design-reasoning docstrings (×2) | done, swept across both files |
| labels named twice | done — `ConfigurationKey` derives the key from `DefaultLabel` |

## Next steps

1. Nothing is outstanding on this branch. It is waiting on review.
2. If the user wants the `TipStatus` inheritance anyway: it costs an encoder for both
   report documents, replacing `asdict` in the two `as_json` methods, and re-checking
   every `document[key] == TipStatus.X` comparison. Measured, not guessed.
3. The reparent onto #151's branch stays wrong until #151 merges `main` — #154 already
   contains #151's head and is 195 commits ahead of it.
4. `needs-resolution` is left for the next maintenance pass to clear itself.

## Worth carrying

- **Two asks in one round can be individually reasonable and jointly impossible.** A
  dataclass field called `name` cannot exist on an enum member, so the rename and the
  inheritance could not both ship. Reporting the conflict beat answering either.
- **A mechanical rename reaches inside names it was never meant to touch.** Two test
  names had been green and meaningless for two rounds after an `a_*` → `create_*` sweep.
- **Single-sourcing a contract deletes its guard.** The commit that gave the report a
  parser is the commit that had to widen the one test standing outside the enum, 8 keys
  to 22.
- **A local test failure can be about `PATH`.** Four hook tests fail in this container
  because `check-setup.sh` probes whichever `python3` is first on `PATH`; they fail at
  the pre-merge head too, and CI is green.
No progress recorded yet for this branch. Initialize it now: a short plan,
what's done so far, and what's next. Keep it current as you work.
