---
name: setup-personal-notes
description: One-time setup for this repo's personal-notes tooling - the personal-notes branch, its remote/branch/path resolution, the plan-dashboard dependencies, the CLAUDE.local.md the SessionStart hook writes, and the pull request labels the tooling uses. Invoke as "/setup-personal-notes". Use when someone is setting up this repo for Claude Code for the first time, when personal notes/PR progress/plan dashboards aren't working, or when another skill's prerequisite check reports the setup is incomplete.
allowed-tools: Bash, Read, AskUserQuestion, mcp__github__get_me, mcp__github__get_label
---

# Set up personal notes

Gets a clone from "I have a fork of this repo and nothing else" to "personal
notes, PR progress and plan dashboards all work."

**Every mechanical step lives in
[`setup-personal-notes.sh`](../../hooks/setup-personal-notes.sh)**, which needs no
session at all. This skill exists for the parts a script cannot supply: the
answers to the questions, and the one piece of the setup that no command can
finish (step 6). So it asks, invokes the script, and reports what came back — it
does not re-implement any step itself.

## 1. Find out what is already done

```bash
source .claude/hooks/resolve-personal-notes-config.sh
bash "${CHECK_SETUP_SCRIPT}" || true
```

Read-only. It prints one tab-separated `<check>` / `<status>` / `<detail>` row per
check and exits non-zero if any row is `needs-setup` (`|| true` keeps that from
ending the block early — the rows are the point, not the status).

Two rows feed the questions below: `notes_remote_url` (where notes would go today)
and `notes_branch` (whether they are already there).

**If it exited 0**, the clone is already set up. Ask nothing: go straight to
step 5 and run the script with the remote that already resolved. That re-checks
the labels — the one thing `check-setup.sh` cannot see — and reports the rest.

## 2. `tooling_files` — the fork is missing the tooling itself

Not fixable from here: their default branch predates the `.claude/` tooling. Tell
them to merge the current default branch into their fork and re-run. Stop; every
later step depends on files this clone doesn't have.

## 3. `session_start_hook` / `claude_local_md_ignored` — a broken checkout

Both come from committed files (`.claude/settings.json`, `.gitignore`), so a
failure means this checkout diverges from the default branch rather than anything
personal being unconfigured. Say which one is off and what restores it
(`git checkout <default-branch> -- .claude/settings.json` / `.gitignore`); ask
before changing a tracked file, since the divergence may be deliberate.

## 4. The questions

**Which remote?** The decision the whole setup turns on: is the notes remote their
own fork, or a shared upstream they cannot push to? Compare the
`notes_remote_url` row against their GitHub login:

```
mcp__github__get_me
```

If the URL's owner is that login, it is already their own fork — use it as the
answer and move on. If it isn't (the common case: `origin` is the shared
upstream), the notes would be pushed somewhere they don't own. Ask where their
notes should live, offering `https://github.com/<their-login>/<repo>` as the
default, and note they may also name a remote already in the clone, or a different
repository entirely.

The script verifies this too, and refuses outright when GitHub says the remote
belongs to someone else. Asking first is nicer than being refused; the script's
check is the backstop, not the interface.

**Starter notes?** Only when there is no notes file yet. Offer
[`starter-notes.md`](./starter-notes.md) — working conventions for pull requests,
review comments and progress tracking — defaulting to yes, and make clear it is a
starting point they own and can edit or discard. Declining leaves an empty file,
which is a perfectly good state.

**Create missing labels?** The tooling reads `merged` and applies `bug` and
`in-review`, and a fresh fork has none of them. Creation writes to their
repository and is visible to everyone who can see it, so ask before passing
`--create-labels`. Defaulting to yes is fine; doing it unasked is not.

Only these three are worth asking. The branch and path have working defaults;
mention that both are overridable (`claude.personalNotesBranch` /
`claude.personalNotesPath`, same three-way precedence) and only ask if they want
something else — for example a distinct branch name so several people sharing one
remote don't collide.

## 5. Run the setup

```bash
bash "${SETUP_PERSONAL_NOTES_SCRIPT}" --remote <chosen-remote-or-url> \
  [--starter-notes] [--create-labels]
```

It points the notes remote at the choice, creates the branch, seeds it if asked,
installs the plan-dashboard dependencies, runs `session-start.sh` so this clone
picks the notes up, checks the labels, and finishes by printing `check-setup.sh`'s
report. Safe to re-run: every step is skipped when already done, and it exits with
the final check's status, so it cannot report a half-finished setup as success.

Relay what it printed — especially any row still `needs-setup` — rather than what
you expected it to print.

**If it reports that it skipped the owner or label checks for lack of
credentials**, that is the one thing this session can do that the script cannot:
there is no `gh` and no `GH_TOKEN`/`GITHUB_TOKEN` in the shell. Do those two
checks over MCP instead — `mcp__github__get_me` for the owner comparison above, and
`mcp__github__get_label` per label (`merged`, `bug`, `in-review`) against the
repository they open pull requests against, where a `404` means missing. There is
no create-label tool in the MCP server, so report which are missing and point them
at `https://github.com/<owner>/<repo>/labels`, or re-run the script somewhere `gh`
is authenticated. Missing labels block nothing else.

## 6. The part no command can finish

**`git config` alone is not enough for sessions that clone fresh every time**
(Claude Code on the web, and any cloud environment): the clone — and its git config
with it — is gone next session. For those, the same values have to be set as
persistent environment variables at the *environment* level, which nothing inside a
session can do. Give them the exact lines, and only the ones that differ from the
defaults:

```
CLAUDE_PERSONAL_NOTES_REMOTE=<chosen-remote-or-url>
CLAUDE_PERSONAL_NOTES_BRANCH=<branch, only if not claude/personal-notes>
CLAUDE_PERSONAL_NOTES_PATH=<path, only if not .claude/personal/cram-notes.md>
```

Point them at their environment's own docs for where that list lives (for Claude
Code on the web: <https://code.claude.com/docs/en/claude-code-on-the-web>), and at
[`personal-notes.env.example`](../../hooks/personal-notes.env.example) and
[`configure-personal-notes.sh`](../../hooks/configure-personal-notes.sh) for the two
shapes that wiring takes. Say so plainly rather than leaving them to discover it
next session when their notes have vanished.

Then tell them what they can now do, briefly: ask for notes edits in any session,
track a PR's progress, and — if the dependencies installed — `/plan-create` and
`/plan-dashboard`, pointing at
[`example-walkthrough.md`](../plan-dashboard/example-walkthrough.md) for the worked
example.

## What this skill must never do

- **Never invent where someone's notes live.** A wrong remote pushes personal notes
  to a repository they didn't choose. Ask, always, unless the resolved remote is
  already provably their own.
- **Never claim the environment-variable half is done.** No command inside a session
  can persist an environment variable for the next fresh clone.
- **Never re-implement a step the script owns.** It is the single definition of what
  setup does; a copy here is how the two drift apart.
- **Never create labels in someone's repository unasked.** Labels are visible to
  everyone who sees the repository; report what's missing and offer.
