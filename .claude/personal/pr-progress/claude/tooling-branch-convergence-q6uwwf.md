## Tooling branch convergence across the bastler move (decision 13)

This session opened no pull request of its own. It brought every open
`.claude/`-side tooling branch across #185's package move so an integration
build can carry both sides, then rebuilt.

### Plan (chosen: rebase, per your preference)

Merge `claude/plan-item-kickoff-workflow-cuare2` (#185) into each open
`.claude/`-side tooling branch, re-apply its delta inside `bastler/`, run
`test/bastler_test`, push, and retarget the pull request's base to the move.

### Done

Crossed and pushed, each with the bastler suite green:

| pull request | tests | base retargeted |
|---|---|---|
| #156, #157, #184, #188, #194, #198, #199, #253, #279 | 666-712 | yes, to #185 |
| #207 -> #273, #277 | 719, 732, 726 | #207 refused; children correct |
| #154 -> #211 -> #260 | 909, 1157, 1175 | #154 refused; children correct |

Rebuild carries 6 tips of 13 (7 pull requests), from 2 of 16 (3) before.
No skip is attributed to the move any more.

### Next / outstanding

- #207 and #154 still have `base = main`. GitHub refuses a base change on a
  pull request it holds in a stack, so both need moving to
  `claude/plan-item-kickoff-workflow-cuare2` by hand.
- #156, #157, #273 are held out of the build by flaky robotics-matrix jobs;
  `test_bastler` is green on all three.
- Descriptions updated for #207, #273, #277; #154 got a comment instead of a
  30 KB rewrite. The other nine still name pre-move paths.
- #281, #282, #285, #291 sit on #154/#211 at their pre-crossing heads and
  need restacking.
- #162 vs #151, #206/#218/#253 vs #184, #260 vs #198, #277 vs #151: the
  remaining build skips, all ordinary pairwise collisions for
  `/integration-conflict-triage`.
