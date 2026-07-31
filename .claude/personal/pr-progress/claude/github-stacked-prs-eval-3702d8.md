Discussion-only session: evaluate GitHub's native stacked-PRs preview (server-side
cascading rebase, gh stack CLI, stack webhooks/REST/GraphQL, stack map UI) against
the workflow-unification plan's hand-rolled stack tooling (#106 stack.py, PR 4
stack-board, the live "PR Stack Monitor and Update" Routine).

Done: read workflow-unification plan.yaml + roadmap.md, surveyed triggers (live
routine is trig_01N79jHmLo3bSbg8pLM6MNTB per roadmap; only enabled trigger on the
first two pages is the poke-only "Refresh Plan Dashboard"). Assessment delivered
in chat: native stacks replace the restack mechanics and much of the board's
visualization role, but not the fork→cram2 promotion doctrine, label hygiene,
fork-main fast-forward, or plan dashboards; cross-fork stacks unsupported (fine
for the in-fork chain, irrelevant to the cram2 hop which was never a stack).

Round 2 (user screenshots + preferences): Stack #112 already exists on the fork —
the seven D-core PRs (#41→#63→#64→#65→#66→#67→#98) adopted into a native stack
trunked on ripple-down-rules-refactor. Proves: preview enabled, post-hoc adoption
("Add to stack") works, non-main trunk works. User decisions recorded: ONE
dashboard only (plans dashboard keeps its buttons/suggested-actions; stack board
half of PR 4 dies; every fork PR must belong to a plan — enforceable as a
dashboard-build invariant); understands the gain as API mechanics + slimming the
Routine, possibly to a plain GitHub Action. My analysis: deterministic duties
(fork-main fast-forward, labels, cram2-link comment, site build) → Action;
mechanics → GitHub native; residue needing a session = cascade conflicts + red
CI after restack — endgame may be no scheduled LLM routine at all, on-demand
sessions instead.

Round 3 (go-ahead given): prototype RUN and CONCLUDED. Host: throwaway proto-*
branches on stack-board (repo creation 403s for the installation token; stack-board
main untouched, trunk was throwaway proto-trunk). All probes conclusive — full
findings + per-item consequences in workflow-unification roadmap.md addendum
2026-07-31; item native-stacks-prototype added (status done); plan saved
(save-plan.sh); dashboard republished same URL. Headlines: all stacks REST
endpoints work from session token under X-GitHub-Api-Version 2026-03-10
(list/get/create/add/unstack; drafts accepted; preview account-wide); GraphQL
blocked session-side (pinned queries) → pr_state must use REST; NO REST cascade
trigger exists (UI-only; update-branch hard-403s "Merging stacked PRs via this
API is not supported") → automation cascades via local rebase+force-push
(verified, preserves stack membership); merges MUST use new async API
PUT /pulls/{n}/merge-async + poll GET .../merge-async/{uuid} (classic merge +
MCP merge tool hard-403 on stacked PRs); mid-stack merge merges everything below
in one op + auto-retargets PRs above (incl. draft) in seconds; stale stack
refused with "not a linear descendant" error; draft merge refused "Pull request
is in draft"; conflicts = plain mergeable:false/dirty; stack base.sha lagging
trunk head = staleness signal; Actions payloads carry .pull_request.stack,
retarget arrives as "edited" action; stack auto-closes when only merged PRs
remain.

Round 4 (recommendations approved, executed): all re-scopes recorded in
plan.yaml + roadmap addendum "2026-07-31 (later)"; #102 comment posted
(issuecomment-5139936707); dashboard republished. Routine audit ran with round-2
probes on rebuilt throwaway stack #6 (reopened PRs #3/#5 on stack-board):
doctrines never API-merge (clean), BUT Phase 1 REPARENT hits 422 on stack
members ("Cannot change the base branch because the pull request is part of a
stack") and push-based merges do NOT auto-retarget children (merge-async does)
— so #106's trim commit must special-case reparent (unstack → PATCH base →
re-stack verified as API-only recovery; gh stack sync / UI Rebase-stack are the
alternatives). gh stack sync documented automation-safe → cutover Action's
cascade step. Round 5 (chain adoption fixed): user's UI attempt produced Stack #113 =
101→106→111 (wrong sibling — blocks #107/#110). Session dissolved it and
created Stack #114 = main→101→106→107(draft)→110(draft), the intended
sequence; #111 verified untouched (loose, sibling of #107). Key correction
learned doing it: POST /stacks/{n}/unstack takes NO body — it DISSOLVES the
stack (no selective removal; merged members stay); reparent recovery is
dissolve → PATCH base → re-create, or gh stack modify for surgery. Fork-side
stack writes worked from the session this round — earlier denials were
permission-layer variance. Recorded in roadmap addendum "2026-07-31
(adoption)"; plan saved; dashboard republished. #101's cram2 landing will now
exercise push-merge/reparent for real: recovery = Rebase-stack button or gh
stack sync until #106's trim commit lands. Round 6 (routine patch + reassessment): drafted the Phase-1 native-stack
amendment for the live Routine; update_trigger REFUSED — the Routine was
created via http_api (web UI) and agents can only update agent-created
triggers. Correction recorded in roadmap ("2026-07-31 (routine patch)"):
manual paste at claude.ai/code/routines is the mechanism for both the interim
amendment and any prompt cutover. Full amended prompt (17.5k original +
amendment appended) delivered to user as a file; user must paste it. Plan
saved; dashboard republished. Reassessment delivered in chat: architecture
confirmed; recommended upgrading #106's trim commit to a full CUT of the
restack subsystem (restack-plan/next/status derivation) — native stacks + gh
stack + Rebase-stack button + the small reparent-recovery script cover it,
preview-less-repo fallback is YAGNI (preview is account-wide; old tooling
branch stays as tagged archive).

Round 7 (CUT approved + PRs notified): decision 11 recorded in plan.yaml
(#106 cut, #110 narrowed, #111 interplay note) + roadmap addendum
"2026-07-31 (cut)"; dashboard republished. Comments posted: #106
(issuecomment-5140224723, the actionable re-scope instruction), #110
(5140225883), #107 (5140226879, heads-up only), #111 (5140229070, stack
chip + interplay), #101 (5140230288, landing/reparent warning), #102
(5140231567, structural record). Cleanup owed by user: delete stack-board
branches proto-trunk, proto-layer-1..4 (PRs #1-#5 closed, stacks #4/#6
closed). Routine prompt: user pasted the amendment — the live Routine now
handles stacked reparents.

Round 8 (conventions): user retracted the "execute #106's cut" instruction
(it stays with its owning session per the re-scope comment; my worktree
removed, nothing changed). Recorded three new conventions in cram-notes.md
(saved): delta recheck of plan/tracking-issue state (idle-prompt, new-task,
and always-before-save-plan triggers; SHA-stamp + git diff mechanics),
action-only PR comment routing (tracking issue always gets the structural
record), and merged/closed-branch cleanup (unsubscribe + delete armed
triggers + stop polling). Added plan item plan-updates-since-helper
(personal-data, not_started, small PR off fork main); roadmap addendum
"2026-07-31 (conventions)"; dashboard republished. Next session of
substance: execute #106's cut per its re-scope comment. No PR from this
session; no code changes on the fork.
