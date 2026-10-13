# Actions budget

## Why this exists

On 2026-10-08 GitHub disabled every workflow on the fork: "GitHub disabled workflows on this
forked repository to reduce the amount of compute that is wasted. Workflows inherited from the
upstream repository often run on schedules or events that aren't needed on a fork."

## What the audit found (300 most recent runs, 2026-10-02 to 2026-10-08)

The fork had 14,660 runs in total. In the audited window:

- **PR CI and PR Examples & Demos were 235 of 300 runs.** Each push to any pull request started CI
  (16 jobs, about 19 minutes) and Examples (8 jobs), so about 24 jobs per push, whatever the push
  changed. A change only under `.claude/` tested all twelve robotics libraries and seven demos. 47
  pull request branches had runs in six days, and over 100 pull requests are open.
- **Integration refresh** ran four times a day on a schedule plus on every CI completion on
  `integration-*` and every ready flip. Each rebuild opens a candidate pull request that runs the
  full 24 jobs. Probes dispatch one run per merge-order prefix, seven at once.
- **Pushes to the fork's `main`** (upstream syncs) re-ran CI, Examples, docs and up to four publish
  checks on code upstream had already tested.
- **Restack fan-out**: one maintenance pass pushes to many branches at once, and each push is a
  full matrix.
- **Workflows that exist only on feature branches** (stack maintenance with a six-hourly cron,
  tooling label, plan dashboards) run on those branches' pull requests without ever having been
  reviewed onto `main`.

Peak load was 60-90 runs and roughly 800-1,500 jobs a day.

## Decisions taken with the user (2026-10-13)

- Draft pull requests run the changed libraries plus their dependents. The full matrix runs on ready
  for review, a `full-ci` label or dispatch.
- The integration pipeline is event-only: no `schedule` anywhere.
- Plan it here, take the fastest route to unblocking, and keep it clean. Prevent a repeat, and add
  monitors and warnings that fire when rates are being exceeded.

## Design

The manifest (`basstler/actions_budget.toml`) is the single statement of what may run, when, and
how much. A test checks every workflow file against it, so a new or changed workflow has to be
declared on purpose. A branch whose workflow does not conform fails that test as soon as it merges
`main`. The monitor reads the same manifest for its budgets, so the declared volume and the
measured volume are compared against one source.

A `pull_request` run uses the workflow files from the pull request's merge ref, so a trigger change
that lands on `main` reaches every open pull request based on `main` straight away. Pull requests
stacked on other branches pick it up on their next restack.

Re-enabling happens before any of the code lands. Every workflow except CI and Upstream reviews is
switched off by hand in the Actions tab, and each is switched back on once its item makes it conform.

## Ordering

`budget-manifest` first: it carries the trigger changes that remove most of the load, and every other
item declares itself against it. `changed-library-matrix` and `usage-monitor` follow in parallel. The
pipeline items are edits to the unlanded pull requests that introduce those workflows, folded in rather
than given branches of their own.
