**Plan tracking (added late — see below).** This work is now tracked as
`workflow-unification` item `sidebar-bug-fix-chips` (track `dashboards`,
status `in_progress`, no PR yet). The manifest entry and a roadmap update were
written *after* the implementation was already pushed, which is backwards: the
user asked for this as a new PR in the workflow-unification plan in their first
message, and the item should have existed before the first edit. Dashboard
republished at the same URL after the save.

**Two process failures recorded on the item.** (1) The plan item was created
after the fact, not before. The session-start hook reported `plan: none` for this
branch and that was read as "no plan applies" rather than "the plan named in the
request has no item for this branch yet". (2) `check-setup.sh` was never run, so
the plan-dashboard dependencies were found one `ModuleNotFoundError` at a time
across two interpreters instead of in a single call. Both were discussed with the
user; hook-level fixes proposed, not yet built.

## Branch `claude/dashboard-bugfix-pr-section-161vf8` — surface bug-fix PRs on the plan dashboard

**Goal.** Make bug-fix pull requests visible in the plan dashboard's "What to
do next" sidebar.

**Design (revised after review).** First attempt was a separate top "Bug fixes"
section with a red outline. Rejected: the sidebar groups items by *action*, and
being a bug fix is not an action — such items already belong in ready-to-start,
blocker-may-be-cleared or ready-to-review. A red outline would also collide with
the existing per-group outlines, which are not mutually exclusive with it. It is
an attribute, so it renders as a small `bug` chip on the entry wherever the item
already appears.

**Done — committed and pushed, all 200 plan-dashboard tests pass.**
- Failing tests first, in a new `# %% DashboardRenderer - bug-fix marking`
  section of `tests/test_build_dashboard.py`.
- `Item.is_bug_fix`, filled in by `DashboardRenderer._classify_items` via a new
  `_pull_request_record_of` lookup + `_is_bug_fix`. Gives the already-defined
  but previously unused `PullRequestLabel.BUG` its first real consumer.
- The four near-identical sidebar group blocks collapsed into one
  `next_step_group` Jinja macro, each call block supplying its own reason line
  so the per-item drift reason and the three fixed reasons share one path.
- `--bug` CSS variable across all four theme blocks, `.next-bug-chip` rule.
- Docs: `SKILL.md`, `.claude/hooks/README.md`'s "labels the dashboard reads",
  `pr-data-fetching.md`.

**Next.**
- No PR opened yet — waiting on the user. When opened: draft, `bug` label,
  session link in the description.
- The committed `example/` plan has no bug-labelled PR, so its screenshots stay
  accurate and were deliberately left alone. If the walkthrough should show the
  chip, `example/pr_data.json` needs a `bug` label and both screenshots need
  regenerating.

**Open question for the user.** They framed this as "more of a filter that we
can apply to show only the bug-fixing ones". Shipped the chip only; an actual
interactive "bug fixes only" toggle is a small follow-up if wanted — ask before
building it.
