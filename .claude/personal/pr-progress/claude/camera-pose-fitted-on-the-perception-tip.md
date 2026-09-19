# PR 265 extraction and rewire

## Plan
1. Audit #265 for commits no pull request's diff contains. [done]
2. Extract the ones that stand on `main` as small pull requests. [done]
3. Fold the ones that only edit an unlanded PR's own files into that PR. [done]
4. Reparent the pull requests based on #265. [partly done - blocked]
5. Report the stranded closed-sub-PR stack. [done]

## Audit result
81 direct commits (reachable from #265, in no PR's own diff).
Method: rev-list 265 --not main, minus each open PR's `head..base` own commits,
minus each closed sub-PR's commits found via its merge commit in 265.
- 8 already covered: #365 #367 #371 #372 #192(x2) #374(merged) #244/#409
- 1 empty bootstrap commit
- 5 extracted as new PRs
- 6 folded into existing PRs
- 61 blocked on files that exist only on 265

## Done
New draft PRs off main (all labelled `bug` except #418):
- #414 collision query waits for a world-model rebuild   (8bbeba2f74)
- #415 place change with no translation claim            (c77d938735)
- #416 annotation read in its own module                 (f5c383a8a5)
- #417 relationship in a buildable collection            (47af620250)
- #418 postgres setup script documented                  (0f7f206f45)   [no bug label]
Fold-ins pushed:
- #256 <- 798a172d98, 06e7af3eb8, a8c66997f3 (clean)
- #244 <- 31c0f3a67e (resolved; dropped 265-only LiftDetector tail)
- #294 <- 13e2104bcc (clean)
- #295 <- 26e73cea5f (resolved; test adapted to branch's assert idiom)
Reparent:
- #419 = #286's work rebuilt on #275 (new branch, force-push was blocked)
Comments posted: #265 ledger, #299 + #355 landing hazards, #244/#256/#294/#295 fold notes.

## Rejected as new PRs, with reasons (do not redo)
- 31c0f3a67e onto main: needs NumericPose window (#244's) -> folded into #244
- 12d806e201 + 0e580a146d: need EventWithEffect/ComesToRestEvent, which exist on
  NO branch but 265 -> blocked, flagged on #295
- b4397c2291: main's GiskardExecutable._execute_simulation has no is_paused
  caller; the caller comes from the `tracy_icra` branch, which has no open PR
- e6c665cec4: byte-identical to #409's compute_containment_ratio
- 5b790a4076: superseded by merged #374 (ConversionOrder)
- 6afc7b33d9 / 7a6f8f7a91: #192 already reads it without the detour

## Next
- Force-push permission is the blocker for reparenting #286 in place and for
  restacking #355's 19-PR chain. Ask before retrying.
- #299 cannot be reparented: needs the #231->#275 and #232/#238 lineages united.
- The real remaining work: revive the 36 closed sub-PRs (#292..#363, ~122
  commits) on top of #262 -> #271 -> #278/#294/#295/#296/#297, then replay the
  61 blocked commits on top.
- No test suite could be run: this container has none of the workspace's Python
  dependencies (no numpy/pytest importable). CI on each PR is the only check.
