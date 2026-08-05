Task: resolve #125, and explain why it is absent from the `workflow-unification`
plan. No code work - this branch carries no commits and needs no pull request.

Findings: #125 was a duplicate pull request on `claude/workflow-unification-git-identity-ppzcyh`
(`d4fdc5b7`, the same commit #126 points at) based on `main` instead of #121, with
GitHub's auto-filled title/body taken from commit `a525d117`. Absent from the plan
because coverage runs branch -> plan-id and item -> pull_request_number only; nothing
maps a pull request back to an item, so a second pull request on a tracked branch is
invisible to every plan surface.

Done: commented on #125 with the reasoning and closed it; recorded the closure in the
`git-identity-from-personal-notes` item's notes and a new roadmap entry
(`Update 2026-08-05 (resolved): #125 ...`), saved to the notes branch and verified
after the write.

Next: republish the `workflow-unification` dashboard. Nothing else outstanding -
#121's conflict against `main` stays with #121, which owns those files' changes.
