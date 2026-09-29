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

**Exit code 0 — set up.** Say nothing about setup at all; carry on. This whole
document is a no-op on a clone that is already set up, and someone who is must
never hear that it ran.

**Non-zero — something is missing.** Do not start the real work, and do not
attempt the individual fixes inline: `/setup-stacked-prs` exists to do exactly
that, and duplicating a piece of it here is how the two drift apart.

1. Say, in a sentence or two, what is missing and that setup is running now —
   from the `needs-setup` rows' own `<detail>` text, not a guess. This is a
   statement, not a question: never ask whether to run the setup.
2. Invoke `/setup-stacked-prs` and let it finish. It asks its own questions for
   the decisions that are genuinely somebody's to make — which repository holds
   the stack, which it is reviewed in, whether to create labels — and does the
   mechanical parts without asking.
3. Re-run the check. If it now exits 0, carry on as though nothing had happened.
   If it still doesn't, report what remains unresolved and stop — do not push on
   into work that will fail later for the same reason.

## Why this runs without being offered first

Whoever reached this document has already said what they want, and the setup is
the only route to it: there is no useful answer to "shall I set this up?" other
than yes, and asking it turns every first run into two turns.

What survives is narrower and stays inside `/setup-stacked-prs`: the choices
with more than one reasonable answer — which repositories the fork and the
upstream are, and whether to create labels everyone who sees the repository will
see — are still asked there, because getting one of those wrong writes somewhere
nobody chose. Running the setup is not that kind of decision; picking its
destination is.

## The one variation: an unattended run

`/stacked-pr-maintenance --non-interactive`, which is how a scheduled Routine
invokes it, cannot follow step 2 — `/setup-stacked-prs` has questions of its own
and there is nobody in the loop to answer them. It therefore **reports and
stops** instead of running the setup:
print the `needs-setup` rows in the run summary, and do not attempt the phases.
A half-set-up clone silently doing half a restack is worse than a run that says
what is missing.
