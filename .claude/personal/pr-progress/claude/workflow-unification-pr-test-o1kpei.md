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
- Remotes resolved **by repository, not by name**: `upstream_repository` is the one
  committed constant, the fork is whichever remote points elsewhere. Zero/several
  candidates raise rather than guess. `stack.py remotes` reports the pair + the exact
  `git remote add` when no upstream remote exists (this checkout's actual case).
