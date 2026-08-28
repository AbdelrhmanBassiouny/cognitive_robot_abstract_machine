## PR #206 - Refresh button in the dashboard masthead

**Plan.** Add one masthead button to a plan dashboard that copies
`/plan-dashboard <plan-id>` to the clipboard, so the page carries the command
that rebuilds it. Shape it as the same affordance the per-item Resume buttons
already are, rather than a second copy-a-command mechanism.

**Done.**
- `CopyableCommand` ABC in `build_dashboard.py` holds label, plan id and the
  `skill_command_name` ClassVar; `ItemAction` and the new
  `RefreshDashboardAction` each derive their own `command`.
- `dashboard.html` gains a shared `copy_command_button` macro used by both the
  item buttons and the masthead button, plus `.refresh-button` /
  `.refresh-hint` styling.
- Three new tests under `# %% DashboardRenderer - dashboard refresh button`,
  each mutation-checked. One existing assertion narrowed from
  `data-action-command="` to `data-action-command="/plan-item` - its page-wide
  reach was incidental to the behaviour it names; recorded on the PR rather
  than done silently.
- SKILL.md and example-walkthrough.md document the button.
- Committed 57e4af4e, pushed, draft PR #206 open, plan item
  `dashboard-refresh-button` saved to the workflow-unification manifest.
- Both dashboards refreshed and republished this session (rdr-refactor
  60a2f66a, workflow-unification 07123af6), rendered from #157's tooling
  merged with this branch so the pages keep the "Show deferred items" toggle.
  URL cache re-checked with `record_dashboard_url.py`: both `changed: false`,
  nothing to push.

**Next / outstanding.**
- `example/screenshots/dashboard-overview.png` predates the button and was not
  regenerated.
- The master index (`/plan-dashboard` with no argument) was not refreshed.
- PR #185 moves `build_dashboard.py` and `templates/dashboard.html` into
  `bastler/`; this is landing order, not a dependency - whoever lands second
  re-applies the delta in the package.
