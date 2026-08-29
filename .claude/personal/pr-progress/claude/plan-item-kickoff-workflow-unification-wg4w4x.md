# red-candidate-localisation — PR #211 (draft), on #154

Plan item `red-candidate-localisation` of `workflow-unification`, `stack-tooling`
track. Branch `claude/plan-item-kickoff-workflow-unification-wg4w4x`, based on
`claude/plan-item-kickoff-workflow-ixbvxl` (#154). Kickoff in `auto` mode,
session https://claude.ai/code/session_0138w5mqzbkyMPtotF7PD59Z.

## What it does

A candidate red on a matrix job names a failing check and nothing else.
`block-branch` cannot localise it — it re-runs the four tooling directories, and
`test_each_lib (<lib>)` lives in the docker matrix. This re-runs the failing
library's own job over each prefix of the merge order and reports which tip's
arrival turned it, as the same `IntegrationTestFailure` the local search
produces.

## Built

All six kickoff steps, then the review round of 2026-08-29 (15 comments,
`e8932eb40` + `0b1d33f5f`). Thirteen threads resolved, two open.

The round is one complaint — structure over strings, parse once, keep the logic
where something can run it — and it produced three modules:

- **`workflow_document.py`** parses a workflow once into named things, so no
  reader indexes into a mapping under keys it spells itself. `WorkflowFile`,
  `TriggerEvent`, `Action`; a step is found by the action it uses rather than by
  `<action>@<version>`.
- **`matrix_libraries.py`** derives the libraries from the matrix job, found by
  fanning out over a matrix rather than by name. The static list matched `ci.yml`
  and was held by nothing.
- **`integration_pipeline.py`** takes the rebuild out of YAML. Every decision was
  about an exit status and none could run outside a runner; the workflow drops
  223 lines to ~107 and calls one command.

Plus `BranchRefspec`/`push_refspec` (and `--force-with-lease` in place of
`--force`), `DispatchField`, a `match` over `LocalisationStep`, `Probe` →
`DispatchedProbe`, `IntegrationExitCode` in its own module, and every
dict-returning report in `.claude/stack/` on `to_json`.

## Found while building

- **The parser caught its own hazard while being written.** A trigger block is
  under `True`, not `"on"` — YAML reads a bare `on` key as the boolean. The first
  version raised `KeyError` on `ci_reusable.yml`. Scattered across fifteen
  readers that failure is silent: each would answer "no triggers".
- **A folded YAML scalar keeps a more-indented continuation verbatim.** The
  `env:` expression parsed into a string with newlines inside the expression
  delimiters while the assertion about it passed. Printing the parsed value found
  it.
- **The two rounds could collide on a probe branch name.** The name carries its
  round now.
- **A contract test over a workflow has to search the right executable surface.**
  Status `14` lives in the step's `if:`, not its shell.
- **A marker search has to match the marker, not a mention of it.** Writing this
  note, a substring search for the PR-progress marker matched the conventions
  paragraph that *describes* it, seventy lines earlier, so the block landed in
  the middle of the prose and `save-pr-progress.sh` reported "already up to date"
  — correctly, since the real section was untouched. Anchor on the whole line.

## Verified

835 tests pass across the four directories CI runs, from 758. CI green on
`test_claude_dev_tooling` at head `0b1d33f5f`. Mutations checked, each caught by
exactly the test naming its rule.

## Open on purpose

- **The 400-line rule.** Everything this round creates obeys it and the 1008-line
  test module is five — but `integration.py` is 2482 lines and this round adds
  484. It was 2064 before this branch, so the split is #154's and already has its
  own thread. Offered, not done.
- **Two of three constants stayed plain**, each naming one thing with one reader.

## Known limit

The end-to-end live run is gated on a build carrying this branch — a
`workflow_dispatch` workflow is only dispatchable once it is on the default
branch. Same bootstrap Part D needed on 2026-08-28. Stated, not closed.

## Next

Nothing outstanding on the branch. Awaiting review.
