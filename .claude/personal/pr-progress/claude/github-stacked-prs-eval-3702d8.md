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

Next: user endorsed prototyping direction; proposed scratch-repo prototype
(7 probes: REST/GraphQL stack reads incl. from session token, stack
create/extend/dissolve, cascade auto-vs-triggered, mid-stack merge via new merge
API, conflict surface, webhook stack payload via dump Action, drafts-in-stack).
Awaiting go-ahead to add a native-stacks-prototype item to workflow-unification
and run the prototype. No PR from this session; no code changes.
