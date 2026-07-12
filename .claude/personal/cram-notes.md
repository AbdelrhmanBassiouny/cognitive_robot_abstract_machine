# Personal Claude Code notes (abdelrhmanbassiouny only)

These are personal workflow preferences for working on this fork, not project
conventions. They live on the `claude/personal-notes` branch only and are pulled
into every session by the `.claude/hooks/session-start.sh` hook (see the
`claude/session-hooks` branch); this file itself must never be merged into `main`.

## Pull requests

- Always open pull requests as **drafts**. Never open a PR as ready-for-review
  by default; mark it ready only when explicitly told to.
- Bug-fix PRs must always carry the **`bug`** label.
- Keep bug-fix PRs focused: one root cause per PR, based off `main`, no
  unrelated cleanup bundled in.
- Always include a link to the session that created the PR in the PR
  description.
- Always subscribe to all events on every PR you open, and handle each event
  with an explanation summary in the session chat.

## Review comments

- Resolve a review comment thread only once you have genuinely done what it
  asked. If instead you need to ask what to do, or you are not taking an
  action, do not resolve it — reply explaining the situation and asking the
  question.
- Always reply to a PR comment explaining what you did before resolving it.

## Before starting work

- Always fetch, pull, and merge from the original repository you cloned (the
  user-owned repository, whether it is a fork of another or not) before
  investigating problems, reacting to events, or implementing features, so
  you are always working from its latest state.

<!--
Add new personal-only rules below this line. Keep each rule short and
imperative, same style as above.
-->
