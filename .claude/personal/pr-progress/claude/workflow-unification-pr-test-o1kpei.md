# Branch retired — all work now on PR #117

This branch's own PR (#133) was folded into #117 and auto-closed as merged into
#117's branch. Nothing further happens here; commits go straight to
`claude/stack-landed-parent-detection`.

## What #117 carries from this session

- Ancestry-based landed-parent detection (`Stack.has_landed_upstream()`), 3 tests.
- `BASE CHANGES GO THROUGH THE GITHUB MCP SERVER` rule; both reparent sites defer to
  it; native-stack step 3 uses the MCP tool.
- SETUP step 0 now fetches `.claude/stack/` instead of asserting it is on `main`
  (it is not) + the header/README no longer describe a paste model.
- `doctrine.py` — `DoctrineLandmark` (dataclass spec + `Enum`), `GitHubMcpTool`,
  `PromptDirective`, `PromptDocument`. Test module now holds zero doctrine literals.
- `POINTER.md` — the registered prompt as a template; its HARD RULES pinned equal to
  `ROUTINE.md`'s (real 15-line/1404-char block, not a vacuous match).
- 12 contract tests total on the prose. **259 tests pass**, was 247 at session start.

## Live-system state, worth not forgetting

The cloud Routine's registered prompt is a pointer that reads
`.claude/stack/ROUTINE.md` from git each run — `origin/main` first, falling back to
**this PR's branch** since `.claude/stack/` is not on `main` yet. So pushing to
`claude/stack-landed-parent-detection` changes the running workflow immediately.

The registered prompt and `POINTER.md` are **not yet identical**: the file adds
"remember which ref you resolved it from", which step 0 now leans on. Harmless
until re-pasted — a run that used the fallback already knows its own ref — but
`POINTER.md` is the canonical text from now on, so re-paste from it, never the
reverse.

PR #41 was repaired earlier: 268 files/+27,825 → 7 files/+1,318, number and thread
kept. Stack #134, seven PRs, trunk `main`.

## Due when #106 lands

- Delete the pointer prompt's `<TOOLING_BRANCH>` fallback (manual paste at
  claude.ai/code/routines), leaving `<FORK_REPOSITORY>` the only placeholder.
- Delete step 0's fetch fallback (ordinary commit).
Neither breaks anything if missed; both are dead weight.

## Open with the developer

Three fork-owner mentions remain in `ROUTINE.md` — step 0's remotes check, and
Phase 3's two cram2 create-link steps. All three are #106's, not #117's, and
unlike #117's they do **not** expire when `.claude/stack/` reaches `main`. Raised
as a comment on #106; the fix is a `fork_repository` key in `stack.toml` rather
than a text edit, since `ROUTINE.md` is executed verbatim and cannot hold a
placeholder. Asked whether to do it there or fold it into #117 — awaiting the call.
The thread on `ROUTINE.md:73` is left unresolved because it carries that question.

## Residue

This branch can be deleted.

