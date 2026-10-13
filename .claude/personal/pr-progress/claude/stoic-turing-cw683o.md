Task: GitHub blocked Actions on the fork (too many runs). Plan to cut and formalize Actions usage.
Done: audited workflows + last ~300 runs (Oct 2-8): ~80% are PR-triggered CI (16 jobs) + Examples (8 jobs)
on every push, no concurrency cancel, no path filters; integration refresh 4x/day + candidate PRs + 7-way probes;
fork-main upstream syncs rerun full CI/docs/publish; workflows living only on feature branches (stack-maintenance 6h cron,
tooling-label, plan-dashboards); stale ones (coraplex_hang_diagnosis, token-probe, board).
Next: discuss plan with user (open questions on draft-PR CI scope, examples trigger, integration cadence, where changes land),
then implement as an Actions budget manifest + test enforcing it, plus per-workflow trigger changes.
