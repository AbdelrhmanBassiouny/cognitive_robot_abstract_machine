# Branch retired twice over — all work now on PR #106

#133 folded into #117; #117 has now folded into **#106**. Both auto-closed as merged
when their head branches became identical to the parent's. Commits go straight to
`claude/stack-tooling-on-main`. This session is subscribed to #106.

## Why #117 collapsed into #106

Every file #117 touched under `.claude/stack/` does not exist on `main` — #106 is what
creates them. So from main's view the two were one addition and the split was an
artifact of writing order. Worse, the pointer resolves `origin/main` **first**, so
landing #106 alone would have swapped the live Routine onto a copy with no orphaned-child
sweep, no named base-change client, no native-stack recovery and board-membership landed
detection: the #41 bug, back silently. Developer agreed and chose the fold.

## What #106 now carries from this session

- Ancestry landed-parent detection (`Stack.has_landed_upstream()`), 3 tests.
- `BASE CHANGES GO THROUGH THE GITHUB MCP SERVER`; both reparent sites defer to it.
- SETUP step 0 fetches `.claude/stack/` instead of asserting it is on `main`.
- `prompt_model.py` (was `doctrine.py`) — `PromptLandmark`, `PromptRule` +
  `RuleSpecification` carrying `refused_client`/`refusal_status_code`, `GitHubMcpTool`,
  `PromptDirective`, `PromptDocument` (`PARAGRAPH_BREAK` is a `ClassVar`). Zero
  doctrine literals in tests; the word "doctrine" is gone from `.claude/stack/`.
- `POINTER.md` — registered prompt as a template; HARD RULES pinned equal to
  `ROUTINE.md`'s (real 15-line/1404-char block).
- `stack.toml` `fork_repository` + `Repository`/`MalformedRepositoryError`; ROUTINE.md
  names no fork owner (was 3 sites), pinned by `test_routine_names_no_fork_of_its_own`
  against the configured value, not a literal.
- **266 tests pass**, was 247 at session start. `test_claude_dev_tooling` green on
  f89a28fc.

## Live-system state, worth not forgetting

The Routine's registered prompt reads `.claude/stack/ROUTINE.md` from git each run —
`origin/main` first, falling back to the tooling branch since `.claude/stack/` is not on
`main`. The fallback branch named in the *registered* prompt is still
`claude/stack-landed-parent-detection`, which is now a dead branch pointing at the same
commit as #106. It resolves today but should be re-pasted to name
`claude/stack-tooling-on-main`.

The registered prompt and `POINTER.md` also differ: the file adds "remember which ref you
resolved it from", which step 0 leans on. `POINTER.md` is canonical — re-paste from it,
never the reverse.

PR #41 repaired earlier: 268 files/+27,825 → 7 files/+1,318, number and thread kept.

## Open

- #107 and #111 are based on `claude/stack-tooling-on-main` and need a restack now that
  it has moved. #110 sits above #107, so it needs it too.
- Pointer-rendering command (`stack.py pointer --fork ... --tooling-branch ...`) handed
  to **#110** by comment — developer's call, overriding my follow-up-PR suggestion,
  because #110 is the setup PR and this is a setup step.
- Due when #106 lands: delete the pointer's `<TOOLING_BRANCH>` fallback (manual paste)
  and step 0's fetch fallback. Neither breaks anything if missed.

