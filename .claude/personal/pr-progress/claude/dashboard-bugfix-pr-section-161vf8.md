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

**Done.**
- Failing tests first, in a new `# %% DashboardRenderer - bug-fix marking`
  section of `tests/test_build_dashboard.py`.
- `Item.is_bug_fix`, filled in by `DashboardRenderer._classify_items` via a new
  `_pull_request_record_of` lookup + `_is_bug_fix`. Gives the already-defined
  but previously unused `PullRequestLabel.BUG` its first real consumer.
- `--bug` CSS variable across all four theme blocks, and the `.next-bug-chip`
  rule.

**Next.**
- Collapse the four near-identical sidebar `<li>` blocks into one
  `next_step_entry(item, reason, show_review_link)` Jinja macro, so the chip has
  a single home rather than four copies.
- Render the chip from that macro; confirm the two "no chip"/"stays in its
  ordinary group" regression tests still hold.
- Update `SKILL.md` and `.claude/hooks/README.md`'s "labels the dashboard reads"
  entry for `bug` now that it drives UI.
- Full `plan-dashboard` suite + `scripts/format_docstrings.py` on changed Python.

**Open question for the user.** They framed this as "more of a filter that we
can apply to show only the bug-fixing ones". Shipping the chip only; an actual
interactive "bug fixes only" toggle is a small follow-up if wanted — ask before
building it.
