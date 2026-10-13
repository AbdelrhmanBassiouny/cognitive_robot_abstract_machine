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

## Open judgment calls

- **Probe search shape.** #211 chose a linear probe search, dispatched in parallel, over bisection on
  purpose: a round then costs one run's wall clock, and bisection would assume a monotonicity that
  linear search does not. This plan proposes trading that for fewer runs. The trade is the user's to
  make on #211, not something to change quietly.
- **Stack maintenance on candidates.** #280's own description records that `stack-maintenance.yml` had
  run 158 times by 2026-10-05, every one a `pull_request` run on an integration candidate, because a
  build carries the workflow and a candidate runs it from its merge ref. The manifest has to declare
  which workflows a candidate may run, not only which triggers each workflow answers.

## budget-manifest: settled plan (2026-10-13, kickoff in auto mode)

Branch `claude/inspiring-pascal-u7ruus` off `main`, draft pull request #503.

**What lands**

- `basstler/actions_budget.toml`: one `[[workflow]]` table per workflow file allowed in the repository,
  including the ones only unlanded branches carry (`integration-refresh`, `integration-checks`,
  `integration-probe` from #211, `stack-maintenance` from #280, `tooling-label` from #284,
  `plan-dashboards` from #218), declared with the triggers they are *meant* to have once their own items
  conform. Each workflow names its concurrency group and whether it cancels, a job timeout ceiling, and
  one entry per trigger with its activity types, jobs per run and expected runs per day.
- `basstler/actions_budget.py`: reads the manifest into dataclasses, reads a workflow file into the same
  shape, and states every way a workflow can break the manifest as a violation of its own type.
- `test/basstler_test/test_actions_budget.py`: unit tests over small workflow files in the test dataset,
  plus the repository test that runs every `.github/workflows/*.yml` on the branch against the manifest.
- Workflow changes on `main`: `timeout-minutes` on every job that runs on a runner; Examples and Demos on
  `ready_for_review`, a `full-ci` label or dispatch for pull requests; CI, Examples, docs and the four
  publish workflows skip a `push` on a fork (`github.event.repository.fork`, so no repository is named);
  update_docker and Upstream reviews unchanged apart from timeouts.

**Decisions taken while settling it**

- *Cancel-in-progress applies to pull-request workflows that run on `synchronize`*, explicitly or through
  GitHub's default activity types. A workflow answering only lifecycle events (`opened`, `closed`,
  `ready_for_review`) has no superseded commit to cancel, and both `integration-refresh` and
  `stack-maintenance` deliberately serialize with `cancel-in-progress: false` so two passes never race.
  The literal reading would have made the `integration-pipeline-event-only` item unable to conform.
- *Jobs that call a reusable workflow carry no `timeout-minutes`*: GitHub rejects the key on a `uses:`
  job. The called workflow's own jobs carry it, and each reusable workflow is declared in the manifest
  under `workflow_call`.
- *Fork guard on root jobs only*: jobs that `need` a skipped job are skipped with it, so the condition
  goes on every job without `needs`.
- Workflows under `.github/workflows/<subdirectory>/` are not read by GitHub and are out of the check.
- The runs-per-day and timeout numbers are first estimates from the audit in this roadmap, recorded in
  the pull request for the user to adjust; the monitor item is what will measure them.

**Overlap**: #501 (basstler src layout) also edits `ci.yml` and `upstream-reviews.yml` and moves every
basstler module. Whoever lands second moves `actions_budget.py`/`.toml` and re-applies the one-line edits.

**Left open**: the roadmap's "Stack maintenance on candidates" call (which workflows an integration
candidate may run) is not settled here; the manifest declares triggers per workflow only.

## budget-manifest: implemented (2026-10-13, b66263166 on #503)

Built as settled above, with two changes from the plan:

- The workflow reader is its own module, `basstler/workflows.py`, beside `basstler/actions_budget.py`, so it
  can converge with #211's `workflow_document.py` when the second of them lands.
- `ProjectLocation.WORKFLOWS` and `PackageLocation.ACTIONS_BUDGET` name the two paths; the package-contract
  test now reads the workflow directory through the former.

Flagged on the PR for the user: Examples no longer runs on a pull request opened ready, which on upstream is
most of them (the item asks for exactly this, and `integration-pipeline-event-only` relies on it). The
timeouts and runs-per-day values are first estimates. Still a draft awaiting review; nothing else outstanding.
