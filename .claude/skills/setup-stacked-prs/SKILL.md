---
name: setup-stacked-prs
description: One-time setup for this repo's stacked-PR workflow - the fork and upstream remotes, the pull request labels its state machine reads, the per-user stack config on the personal-notes branch, the Routine prompt to paste, and either install mode (tooling on the target repo's own default branch, or overlaid onto a branch of your fork). Invoke as "/setup-stacked-prs". Use when someone is setting the stacked-PR workflow up for the first time, when the stack tooling or its routine isn't working, or when a prerequisite check reports the stack setup is incomplete.
allowed-tools: Bash, Read, AskUserQuestion, mcp__github__get_me, mcp__github__get_label
---

# Set up the stacked-PR workflow

Gets a clone from "I have a fork and the tooling" to "the stack workflow runs on
it."

**Every mechanical step lives in
[`setup-stacked-prs.sh`](../../hooks/setup-stacked-prs.sh)**, which needs no
session at all. This skill exists for the parts a script cannot supply: the
answers to the questions, and the two steps no command can finish (step 5). So it
asks, invokes the script, and reports what came back — it does not re-implement
any step itself.

## 1. The personal-notes prerequisite

The per-user stack config lives on the personal-notes branch, so that setup comes
first. Follow
[`setup-personal-notes/prerequisite-check.md`](../setup-personal-notes/prerequisite-check.md)
before anything else here.

## 2. Find out what is already done

```bash
source .claude/hooks/resolve-personal-notes-config.sh
bash "${CHECK_STACK_SETUP_SCRIPT}" || true
```

Read-only. One tab-separated `<check>` / `<status>` / `<detail>` row per check,
exiting non-zero if any row is `needs-setup` (`|| true` keeps that from ending the
block early — the rows are the point, not the status).

Three rows feed the questions below: `stack_configuration` (which remote names the
workflow expects), `fork_remote` / `upstream_remote` (whether they resolve here),
and `stack_tooling_files` (whether this checkout carries the tooling at all).

**If it exited 0**, the clone is already set up. Ask nothing beyond the fork and
upstream it already resolved, and run the script with those — that re-checks the
labels, the one thing `check-stack-setup.sh` cannot see, and reports the rest.

## 3. `stack_tooling_files` — this checkout doesn't carry the tooling

Two different situations, and the answer differs:

- **The repository is one whose default branch has the tooling**, and this
  checkout is just behind: tell them to merge the default branch and re-run.
- **The repository will never carry it** (its maintainers won't take `.claude/`
  tooling upstream): that is what `--mode fork-overlay` is for. Ask which case
  they are in rather than assuming; a fork-overlay install on a repo that could
  have taken it natively leaves a branch to maintain forever.

## 4. The questions

**Which fork, and which upstream?** The script requires both and guesses neither:
a wrong fork points the whole workflow at a repository they may not own. Offer the
clone's existing remotes as defaults where they look right. Compare the fork
against their GitHub login:

```
mcp__github__get_me
```

The script verifies this too, and refuses outright when GitHub says the fork
belongs to someone else. Asking first is nicer than being refused; the script's
check is the backstop, not the interface.

**Native or fork-overlay?** See step 3. Default to native.

**Any setting that differs for them?** The committed `stack.toml` names the
remotes and labels; a contributor whose remotes are named differently overrides
them for themselves with `--personal-config <key>=<value>`, repeatable. Only ask
if the check reported a remote missing under the name the configuration expects —
their remote may simply be called something else, in which case renaming the
config is better than adding a duplicate remote.

**Create the missing labels?** The workflow reads and writes `in-review`,
`rebase`, `needs-resolution` and `cram2-link-sent`, and a fresh fork has none of
them. Creation writes to their repository and is visible to everyone who can see
it, so ask before passing `--create-labels`. Defaulting to yes is fine; doing it
unasked is not.

## 5. Run the setup

```bash
bash "${SETUP_STACKED_PRS_SCRIPT}" --fork <name-or-url> --upstream <name-or-url> \
  [--mode fork-overlay] [--overlay-branch <name>] \
  [--personal-config <key>=<value>]... [--create-labels]
```

It names the remotes, records only the overrides that actually differ from the
committed defaults, fetches the upstream base, installs the overlay branch when
asked, checks the labels, prints the Routine prompt, and finishes by printing
`check-stack-setup.sh`'s report. Safe to re-run: every step is skipped when
already done, and it exits with the final check's status, so it cannot report a
half-finished setup as success.

Relay what it printed — especially any row still `needs-setup` — rather than what
you expected it to print.

**If it reports that it skipped the owner or label checks for lack of
credentials**, that is the one thing this session can do that the script cannot:
there is no `gh` and no `GH_TOKEN`/`GITHUB_TOKEN` in the shell. Do those checks
over MCP instead — `mcp__github__get_me` for the owner comparison, and
`mcp__github__get_label` per label against the fork, where a `404` means missing.
There is no create-label tool in the MCP server, so report which are missing and
point them at `https://github.com/<owner>/<repo>/labels`, or re-run the script
somewhere `gh` is authenticated.

## 6. The two parts no command can finish

**Paste the Routine prompt.** The script printed it with their remotes filled in;
it goes into <https://claude.ai/code/routines> as the prompt of a scheduled
Routine. Nothing inside a session can create or edit that, so say so plainly
rather than leaving them to discover the workflow does nothing on its own. The
canonical copy is [`routine-prompt.md`](../../stack/routine-prompt.md), and the
doctrine it points at is [`ROUTINE.md`](../../stack/ROUTINE.md).

**Bootstrap the board, if they want one.** The script printed the steps: an empty
repository of their own with GitHub Pages enabled, and its repository variables
set for the fork, the branch and the upstream. The publishing workflow itself is
not shipped yet — it arrives with the stack-board Pages work — so there is
nothing to install into that repository today, and this skill writes nothing to
it. Say that rather than implying the board will start updating.

Then tell them what they can now do, briefly: open each pull request with its
parent branch as the base, un-draft one to approve it for review, and run
`python .claude/stack/stack.py status` / `next` to see the stack and what is
promotable — pointing at [`README.md`](../../stack/README.md) for the loop.

## What this skill must never do

- **Never guess which fork the stack lives on.** A wrong fork points every push
  and every promotion at a repository they didn't choose. Ask, always, unless the
  resolved remote is provably their own.
- **Never repoint an existing remote.** Adding a missing one is setup; silently
  changing where an existing name pushes is a trap. The script only ever adds,
  and reports the mismatch otherwise.
- **Never create labels in someone's repository unasked.** They are visible to
  everyone who sees the repository; report what's missing and offer.
- **Never claim the Routine half is done.** No command inside a session can create
  or edit a Routine.
- **Never re-implement a step the script owns.** It is the single definition of
  what setup does; a copy here is how the two drift apart.
