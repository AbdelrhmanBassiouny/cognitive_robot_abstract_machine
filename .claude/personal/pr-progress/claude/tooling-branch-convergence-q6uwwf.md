## Tooling branch convergence across the bastler move (decision 13)

This session opened no pull request of its own. It brought every open
`.claude/`-side tooling branch across #185's package move so an integration
build can carry both sides, rebuilt, then unified the duplicate dependency
declaration the crossing had left behind.

### Plan (chosen: rebase, per your preference)

Merge `claude/plan-item-kickoff-workflow-cuare2` (#185) into each open
`.claude/`-side tooling branch, re-apply its delta inside `bastler/`, run
`test/bastler_test`, push, and retarget the pull request's base to the move.

### Done

Crossed and pushed, each with the bastler suite green:

| pull request | tests | base |
|---|---|---|
| #156, #157, #184, #188, #194, #198, #199, #253, #279 | 666-712 | retargeted to #185 |
| #207 -> #273, #277 | 703, 716, 710 | all three correct |
| #154 -> #211 -> #260 | 909, 1157, 1175 | all three correct |

Rebuild carries 6 tips of 13 (7 pull requests), from 2 of 16 (3) before.
No skip is attributed to the move any more.

**#207 and #154 are unstacked and retargeted.** You unstacked them, the base
change then went through, and bringing each current on the moved base cut
their diffs from 145 files to 9 and from 187 to 71 - the move no longer shows
in either. GitHub reported both `dirty` in between; that was them sitting
three commits behind the new base, not a real conflict.

**The unification is done, on #207.** `.claude/hooks/requirements.txt` and
`bastler/missing_requirements.py` are gone; `plan-size-report.sh` asks the
`missing_dependencies` helper that `check-setup.sh` and `session-start.sh`
already share, so `bastler/pyproject.toml` is the one declaration. 703 tests,
mutation-checked; the removed module's coverage is already in
`test_dependencies.py` bar one case, which was added there. #273 and #277
restacked onto it.

### Next / outstanding

- #154's description still says "the base stays `main` until #151 catches
  up" - stale since the retarget. Wants a hand edit or a full retype.
- #156, #157, #273 are held out of the build by flaky robotics-matrix jobs;
  `test_bastler` is green on all three.
- Nine crossed descriptions still name pre-move paths: #156, #157, #184,
  #188, #194, #198, #199, #253, #279. #211 and #260 got nothing either.
- #281, #282, #285, #291 sit on #154/#211 at their pre-crossing heads and
  need restacking.
- `integration_test_command` in `bastler/stack.toml` still names the three
  pre-move test directories, so every build this session ran used
  `--no-test`. It wants the bastler suite.
- `.gitignore` still excepts `.claude/hooks/tests/fixtures/set-up-clone/**/*.txt`,
  a path the move deleted and no fixture needs. Left for #185, not #207.
- #162 vs #151, #206/#218/#253 vs #184, #260 vs #198, #277 vs #151: the
  remaining build skips, all ordinary pairwise collisions for
  `/integration-conflict-triage`.
- #207 and #154 are out of draft. Neither was re-drafted after these pushes,
  because a draft is excluded from every integration build - which is the
  process this whole session was fixing. Say the word and I will draft them.
