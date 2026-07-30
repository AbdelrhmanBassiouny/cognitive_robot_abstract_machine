# Prerequisite check: is the stacked-PR workflow set up here?

The stack tooling assumes a setup a clone may simply not have: the fork and
upstream remotes its configuration names, the labels its state machine reads,
and a board that can never be committed. Without this check that shows up as a
confusing mid-run failure — a `git ls-remote` against a remote that isn't there,
a label write that 404s halfway through a promotion — rather than as one clear
answer up front.

The procedure lives here, once, so every consumer references it in a line rather
than restating it. Its personal-notes counterpart is
[`setup-personal-notes/prerequisite-check.md`](../setup-personal-notes/prerequisite-check.md);
run that one first where both apply, since the per-user stack config lives on the
personal-notes branch.

## The procedure

Run this **before** any stack work:

```bash
source .claude/hooks/resolve-personal-notes-config.sh
bash "${CHECK_STACK_SETUP_SCRIPT}" || true
```

**Exit code 0 — set up.** Say nothing about setup at all; carry on. Someone who
is already set up must never be asked about it.

**Non-zero — something is missing.** Do not attempt the individual fixes inline:
`/setup-stacked-prs` exists to do exactly that, and duplicating a piece of it
here is how the two drift apart.

1. Say, in a sentence or two, what is missing and why the work needs it — from
   the `needs-setup` rows' own `<detail>` text, not a guess.
2. Ask, via `AskUserQuestion`, whether to run the setup now. Running it is not a
   decision to make for them: it adds remotes, can write to their fork, and can
   create labels everyone who sees the repository will see.
3. **If they accept:** invoke `/setup-stacked-prs`, let it finish, re-run the
   check, and continue if it now exits 0. If it doesn't, report what remains
   unresolved and stop.
4. **If they decline:** stop, and say plainly what won't work without it.

## The one variation: an automated Routine

A Routine running `ROUTINE.md` cannot follow steps 2 to 4 — its own hard rules
forbid it from entering plan mode or opening a discussion, and there is nobody
in the loop to answer. It therefore **reports and stops** instead of offering:
print the `needs-setup` rows in the run summary, and do not attempt the phases.
A half-set-up clone silently doing half a restack is worse than a run that says
what is missing.
