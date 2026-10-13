# workflow-cutover — standing rules

- The site lives on a regenerated branch. The workflow runs from the fork's default branch, which is the integration branch, and that branch is rebuilt from scratch - a rebuild that drops the tip carrying the workflow takes it off the default branch and manual dispatch stops being offered until a later build carries it again.
- The base-change credential is unverified in the Action. A session's own git-proxy credential refuses a base change while its MCP client performs one; the Action's credential is a third identity again. Verify it with a real base change before relying on it.
- Two operations stay outside the harness. Tag pushes and branch deletes get a 403 through a session's git proxy and no tool substitutes, so `tooling-branch-retirement`'s last two steps are the user's to run. A session can do every verification and prepare the exact commands.
