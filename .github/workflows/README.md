# Workflow Local Testing Guide

This README describes how to test GitHub Actions workflows locally using [act](https://github.com/nektos/act) and [actionlint](https://github.com/rhysd/actionlint). 

## Tools Setup

### 1. act (GitHub Actions Local Runner)
Installs: 
- Docker [install guide](https://docs.docker.com/get-docker/)
- `act` tool: run `curl --proto '=https' --tlsv1.2 -sSf https://raw.githubusercontent.com/nektos/act/master/install.sh | sudo bash`

Usage Example:
```bash
# Run coraplex workflow locally
act -W .github/workflows/coraplex-publish-to-pypi.yml
```

or run a single job:

```bash
act -W .github/workflows/krrood-publish-to-pypi.yml -j "check-version"
```

### 2. actionlint (Workflow Linter)
Installs:
- Go: go to [go website](https://go.dev/doc/install), download and install go
- `actionlint` tool: `go install github.com/rhysd/actionlint/cmd/actionlint@latest`, restart terminal session afterwards

Usage Example:
```bash
# Lint all workflow YAML files
actionlint .github/workflows/*.yml
```

## Workflow Testing Workflow
1. **Linting:** Run `actionlint` to ensure there are no syntax or logical errors in the YAML files.
2. **Local Execution:** Use `act` to simulate the workflow execution and verify that scripts (like version checks) behave as expected in a containerized environment.


## The Actions budget

`test/basstler_test/test_actions_budget.py` holds every workflow in this directory to rules basstler applies
to any repository. A workflow fails it when it:

- runs on a `schedule`;
- runs on every pull-request push without a concurrency group that cancels the superseded run;
- has a job that takes a runner without `timeout-minutes`, or above its ceiling;
- answers `push` without its first jobs skipping a push to a fork;
- answers `labeled` without its first jobs comparing `github.event.label.name`;
- runs on every push (each pull-request push, or a push to any branch) with more jobs than its ceiling,
  counting every matrix combination and every job of a reusable workflow it calls.

The ceilings live in `.github/actions_budget.py`, whose `actions_budget()` returns an `ActionsBudget`:
limits for every workflow, and the limits of each workflow whose own differ. A new workflow needs no entry
until it needs a limit raised, and an entry naming a workflow file that does not exist fails the test.
`python -m basstler.actions_budget` writes a first version of the file from the workflows as they are;
after that it is edited by hand.
