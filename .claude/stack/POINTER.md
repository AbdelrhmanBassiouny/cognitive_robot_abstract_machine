# The registered pointer prompt

What is registered at claude.ai/code/routines is not the routine document itself but the short prompt
below. It resolves `.claude/stack/ROUTINE.md` out of git and executes what it finds there, so the
workflow is changed by pushing rather than by re-pasting into the Routine settings page.

The prompt is kept here because it is the one piece of the workflow that lives outside the
repository. Without a canonical copy the running prompt would be its own only record - the drift
this directory exists to prevent, one level up. Its HARD RULES are pinned by
`tests/test_prompt_documents.py` against `ROUTINE.md`'s own copy, so the two cannot diverge.

**Editing this file does not change the running Routine.** The block below has to be re-registered
by hand when it changes; that is the cost of the rules having to bind before any file is read, since
a webhook event can arrive before the first tool call.

To use this workflow on your own fork, substitute `<FORK_REPOSITORY>` with your `owner/repository`
and `<TOOLING_BRANCH>` with the branch carrying `.claude/stack/`, then register the block.

They are substituted here, in the copy you paste, rather than read from `stack.toml` at run time:
this prompt runs *before* the repository is readable - resolving the routine document is the first
thing it does - so it cannot look anything up.

```text
Run the stacked-PR maintenance routine for <FORK_REPOSITORY>.

Read `.claude/stack/ROUTINE.md` from git and execute the fenced text block inside it as your
instructions for this run - it is the whole job, and everything past the rules below is in there.
Resolve it from `origin/main`. If `.claude/stack/` is not on `main` yet, resolve it from
<TOOLING_BRANCH> instead; either way, remember which ref you resolved it from, because that
document's SETUP step 0 asks you for it. (Delete this fallback once `.claude/stack/` is on `main`.)

Do not summarise it back to me, do not ask which phase to begin with, and do not wait for
confirmation - read it and run it.

HARD RULES so you never drift into review work:
- NEVER call `subscribe_pr_activity`, and never stay subscribed - you learn CI by POLLING (Phase 2/SETUP).
- If a review, review-comment, issue-comment, or any `<github-webhook-activity>` event is ever delivered
  to you, your ONLY valid action is to END THE TURN immediately: do not investigate it, do not draft or
  post a plan, do not reply, do not ask the developer to confirm anything. The one exception is a CI/check
  *status* you were polling for your own restack.
- NEVER enter plan mode or post a "here's my plan" comment. You either perform a mechanical step from the
  phases below or you stop; you never open a discussion.
- LABELS ARE REPLACE, NOT ADD: the GitHub label-write call takes the PR's **entire** new label set - it
  does not add to what's already there. "Add `in-review`" or "remove `cram2-link-sent`" NEVER means
  calling it with just that one label. Every single label write, in every phase, is: (1) read the fork
  PR's CURRENT labels, (2) compute the full new set - union with the label you're adding, or the current
  set minus the label you're removing - (3) call the label write with that complete list. Skipping step 1
  silently wipes every other label on the PR (this has happened before and deleted `in-review` off
  already-promoted PRs, making the routine wrongly re-suggest branches that were already under review).
```
