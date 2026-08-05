## claude/stacking-branch-switch-issue-v1kzqq - stack tooling vanishing on branch switch

**Problem (diagnosed, confirmed):** `.claude/stack/` is *tracked repo content*, so any
`git checkout <stack-branch>` during a restack deletes it from the working tree. 126 of 146
fork branches predate the tooling merge, so this is the normal case, not an edge case.
Secondary: the step-0 recovery `git checkout <ref> -- .claude/stack/` leaves the files
*staged* - a restack merge commit would swallow the tooling into a feature branch and then
upstream. `board.json` is neither tracked nor gitignored, same exposure.

**Plan:**
1. [done] Diagnose + reproduce (index-pollution repro in scratchpad).
2. [next] Decide mitigation with the developer - preferred: stage the tooling into an
   out-of-tree run directory at step 0 and invoke it from there for the whole pass, so no
   branch switch can reach it; plus restore the starting branch at the end of the pass.
3. [ ] Failing test in `.claude/stack/tests/` first, then the SKILL.md / stack.py change.
4. [ ] Gitignore `board.json`.

**Next:** awaiting developer's choice of mitigation shape before writing code.
