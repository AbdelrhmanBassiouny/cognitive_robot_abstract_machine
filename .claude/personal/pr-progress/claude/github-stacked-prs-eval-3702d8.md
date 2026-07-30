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

Next: user decides between land-then-migrate vs pivot-now for #106/#110/#111 and
whether to re-scope PR 4 / routine-cutover around the native feature. No PR from
this session; no code changes.
